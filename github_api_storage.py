import os
import base64
import logging
import requests
from typing import Any, List, Optional
from storage import FileStorage


class GitHubAPIStorageError(Exception):
    """Custom exception for GitHub API storage errors."""
    pass


class GitHubAPIFileStorage(FileStorage):
    """File storage implementation using GitHub API for repository contents.
    
    This implementation avoids git rebase issues by using direct API calls
    for all file operations. Each write operation is atomic and uses SHA-based
    optimistic locking to prevent conflicts.
    """
    
    def _validate_path(self, path: str):
        if not isinstance(path, str) or not path.strip():
            logging.error(f"GitHubAPIFileStorage: Invalid file path: '{path}'")
            raise ValueError(f"Invalid file path: '{path}'")
    
    def __init__(self, owner: str, repo: str, branch: str = "main", token: Optional[str] = None):
        """Initialize GitHub API storage.
        
        Args:
            owner: Repository owner (username or organization)
            repo: Repository name
            branch: Branch name (default: "main")
            token: GitHub personal access token (if not provided, uses GITHUB_TOKEN env var)
        """
        self.owner = owner
        self.repo = repo
        self.branch = branch
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GIT_STORAGE_TOKEN")
        
        if not self.token:
            logging.warning("GitHub API token missing; repository may be read-only")
        
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"
        
        # Cache for file SHAs to enable updates
        self._sha_cache = {}
    
    def _get_api_url(self, path: str) -> str:
        """Construct GitHub API URL for a file path."""
        clean_path = path.lstrip("/")
        return f"{self.base_url}/repos/{self.owner}/{self.repo}/contents/{clean_path}"
    
    def _get_file_sha(self, path: str) -> Optional[str]:
        """Get the current SHA of a file from the API."""
        try:
            url = self._get_api_url(path)
            params = {"ref": self.branch}
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("sha")
            elif response.status_code == 404:
                return None  # File doesn't exist
            else:
                logging.warning(f"Failed to get SHA for {path}: {response.status_code}")
                return None
        except Exception as e:
            logging.error(f"Error getting SHA for {path}: {e}")
            return None
    
    def read(self, path: str, mode: str = "r", encoding: Optional[str] = None) -> Any:
        """Read file contents from GitHub API.
        
        Args:
            path: File path relative to repository root
            mode: File mode ('r' for text, 'rb' for binary)
            encoding: Text encoding (used when mode='r')
            
        Returns:
            File contents as string (text mode) or bytes (binary mode)
        """
        self._validate_path(path)
        
        try:
            url = self._get_api_url(path)
            params = {"ref": self.branch}
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 404:
                raise FileNotFoundError(f"File not found: {path}")
            
            response.raise_for_status()
            data = response.json()
            
            # Cache the SHA for potential future updates
            self._sha_cache[path] = data.get("sha")
            
            # Decode base64 content
            content_b64 = data.get("content", "")
            content_bytes = base64.b64decode(content_b64)
            
            if "b" in mode:
                return content_bytes
            else:
                return content_bytes.decode(encoding or "utf-8")
                
        except requests.exceptions.RequestException as e:
            logging.error(f"GitHub API request failed for {path}: {e}")
            raise GitHubAPIStorageError(f"Failed to read {path}: {e}") from e
    
    def write(self, path: str, data: Any, mode: str = "w", encoding: Optional[str] = None) -> None:
        """Write file contents using GitHub API.
        
        Args:
            path: File path relative to repository root
            data: Content to write (string or bytes)
            mode: File mode ('w' for text, 'wb' for binary)
            encoding: Text encoding (used when mode='w')
        """
        self._validate_path(path)
        
        try:
            # Convert content to bytes if needed
            if isinstance(data, str):
                content_bytes = data.encode(encoding or "utf-8")
            else:
                content_bytes = data
            
            # Encode to base64
            content_b64 = base64.b64encode(content_bytes).decode("ascii")
            
            # Get current SHA if file exists (required for updates)
            sha = self._sha_cache.get(path) or self._get_file_sha(path)
            
            # Prepare API request
            url = self._get_api_url(path)
            payload = {
                "message": f"Update {path}",
                "content": content_b64,
                "branch": self.branch
            }
            
            if sha:
                payload["sha"] = sha  # Required for updates
            
            # Retry up to 3 times on conflict
            max_retries = 3
            for attempt in range(max_retries):
                response = requests.put(url, headers=self.headers, json=payload, timeout=30)
                
                if response.status_code == 409:
                    if attempt < max_retries - 1:
                        # Conflict - file was modified since we read it
                        logging.warning(f"Conflict writing {path}, retrying ({attempt + 1}/{max_retries}) with fresh SHA")
                        # Retry with fresh SHA
                        sha = self._get_file_sha(path)
                        if sha:
                            payload["sha"] = sha
                        else:
                            # File might have been deleted
                            logging.error(f"Cannot get SHA for {path} on retry {attempt + 1}")
                            break
                    else:
                        # Final retry failed
                        logging.error(f"Failed to write {path} after {max_retries} attempts due to conflicts")
                        response.raise_for_status()
                else:
                    # Success or other error
                    break
            
            response.raise_for_status()
            
            # Update SHA cache
            result = response.json()
            if "content" in result and "sha" in result["content"]:
                self._sha_cache[path] = result["content"]["sha"]
                logging.info(f"Successfully wrote {len(content_bytes)} bytes to {path}")
            else:
                logging.warning(f"Write response for {path} missing content/sha: {result}")
                
        except requests.exceptions.RequestException as e:
            logging.error(f"GitHub API request failed for {path}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logging.error(f"Response status: {e.response.status_code}, body: {e.response.text[:500]}")
            raise GitHubAPIStorageError(f"Failed to write {path}: {e}") from e
    
    def remove(self, path: str) -> None:
        """Delete a file using GitHub API.
        
        Args:
            path: File path relative to repository root
        """
        self._validate_path(path)
        
        try:
            # Get current SHA (required for deletion)
            sha = self._sha_cache.get(path) or self._get_file_sha(path)
            
            if not sha:
                logging.warning(f"Cannot delete {path}: file not found or SHA unavailable")
                return
            
            url = self._get_api_url(path)
            payload = {
                "message": f"Remove {path}",
                "sha": sha,
                "branch": self.branch
            }
            
            # Retry up to 3 times on conflict
            max_retries = 3
            for attempt in range(max_retries):
                response = requests.delete(url, headers=self.headers, json=payload, timeout=30)
                
                if response.status_code == 409:
                    if attempt < max_retries - 1:
                        # Conflict - try with fresh SHA
                        logging.warning(f"Conflict deleting {path}, retrying ({attempt + 1}/{max_retries}) with fresh SHA")
                        sha = self._get_file_sha(path)
                        if sha:
                            payload["sha"] = sha
                        else:
                            # File might have been deleted by another process
                            logging.warning(f"File {path} appears to have been deleted already")
                            return
                    else:
                        # Final retry failed
                        logging.error(f"Failed to delete {path} after {max_retries} attempts due to conflicts")
                        response.raise_for_status()
                else:
                    # Success or other error
                    break
            
            response.raise_for_status()
            
            # Clear from cache
            self._sha_cache.pop(path, None)
            
        except requests.exceptions.RequestException as e:
            logging.error(f"GitHub API request failed for {path}: {e}")
            raise GitHubAPIStorageError(f"Failed to remove {path}: {e}") from e
    
    def exists(self, path: str) -> bool:
        """Check if a file exists in the repository.
        
        Args:
            path: File path relative to repository root
            
        Returns:
            True if file exists, False otherwise
        """
        self._validate_path(path)
        
        try:
            url = self._get_api_url(path)
            params = {"ref": self.branch}
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Error checking existence of {path}: {e}")
            return False
    
    def makedirs(self, path: str, exist_ok: bool = True) -> None:
        """GitHub doesn't require explicit directory creation.
        
        Directories are created implicitly when files are added.
        This is a no-op for API compatibility.
        """
        # No-op: GitHub creates directories implicitly
        pass
    
    def listdir(self, path: str) -> List[str]:
        """List contents of a directory.
        
        Args:
            path: Directory path relative to repository root
            
        Returns:
            List of filenames in the directory
        """
        self._validate_path(path)
        
        try:
            url = self._get_api_url(path)
            params = {"ref": self.branch}
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 404:
                raise FileNotFoundError(f"Directory not found: {path}")
            
            response.raise_for_status()
            data = response.json()
            
            # If it's a directory, data will be a list
            if isinstance(data, list):
                return [item["name"] for item in data]
            else:
                # Single file, not a directory
                raise NotADirectoryError(f"Not a directory: {path}")
                
        except requests.exceptions.RequestException as e:
            logging.error(f"GitHub API request failed for {path}: {e}")
            raise GitHubAPIStorageError(f"Failed to list {path}: {e}") from e
