import os
import tempfile
import logging
from typing import Any, List, Optional
from storage import FileStorage
from git import Repo, GitCommandError

class GitStorageError(Exception):
    """Custom exception for git storage errors."""
    pass

class GitFileStorage(FileStorage):
    def _validate_path(self, path: str):
        if not isinstance(path, str) or not path.strip():
            import logging
            logging.error(f"GitFileStorage: Invalid file path: '{path}'")
            raise ValueError(f"Invalid file path: '{path}'")

    def __init__(self, repo_url: str, branch: str = "main"):
        self.repo_url = repo_url
        self.branch = branch
        self.local_dir = tempfile.mkdtemp(prefix="git_storage_")
        if not os.path.exists(os.path.join(self.local_dir, ".git")):
            self.repo = Repo.clone_from(self.repo_url, self.local_dir, branch=self.branch)
        else:
            self.repo = Repo(self.local_dir)
        self.repo.git.checkout(self.branch)

    def _full_path(self, path: str) -> str:
        self._validate_path(path)
        return os.path.join(self.local_dir, path.lstrip("/"))

    def read(self, path: str, mode: str = "r", encoding: Optional[str] = None) -> Any:
        self._validate_path(path)
        full_path = self._full_path(path)
        with open(full_path, mode, encoding=encoding) as f:
            return f.read()

    def write(self, path: str, data: Any, mode: str = "w", encoding: Optional[str] = None) -> None:
        self._validate_path(path)
        full_path = self._full_path(path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        try:
            with open(full_path, mode, encoding=encoding) as f:
                f.write(data)
            self.repo.git.add(full_path)
            self.repo.index.commit(f"Update {path}")
            # Always pull before pushing to avoid non-fast-forward errors
            self.repo.git.fetch("origin", self.branch)
            self.repo.git.pull("origin", self.branch)
            self.repo.git.push("origin", self.branch)
        except GitCommandError as e:
            logging.error(f"Git operation failed during write for {path}: {e}")
            # Optionally, notify the user via a custom exception
            raise GitStorageError(f"Failed to write {path} due to a git error. The operation was not completed. Please check the repository status.") from e
        except Exception as e:
            logging.error(f"Unexpected error during write for {path}: {e}")
            raise

    def remove(self, path: str) -> None:
        self._validate_path(path)
        full_path = self._full_path(path)
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
                self.repo.git.add(full_path)
                self.repo.index.commit(f"Remove {path}")
                # Always pull before pushing to avoid non-fast-forward errors
                self.repo.git.fetch("origin", self.branch)
                self.repo.git.pull("origin", self.branch)
                self.repo.git.push("origin", self.branch)
            except GitCommandError as e:
                logging.error(f"Git operation failed during remove for {path}: {e}")
                raise GitStorageError(f"Failed to remove {path} due to a git error. The operation was not completed. Please check the repository status.") from e
            except Exception as e:
                logging.error(f"Unexpected error during remove for {path}: {e}")
                raise

    def exists(self, path: str) -> bool:
        self._validate_path(path)
        return os.path.exists(self._full_path(path))

    def makedirs(self, path: str, exist_ok: bool = True) -> None:
        self._validate_path(path)
        os.makedirs(self._full_path(path), exist_ok=exist_ok)
        # Optionally commit directory creation (git tracks files, not empty dirs)

    def listdir(self, path: str) -> List[str]:
        self._validate_path(path)
        full_path = self._full_path(path)
        return os.listdir(full_path)