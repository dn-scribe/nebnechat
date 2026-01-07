import os
from typing import Optional
from local_storage import LocalFileStorage
from github_api_storage import GitHubAPIFileStorage
from storage import FileStorage

def get_storage() -> FileStorage:
    """Get the appropriate storage backend based on environment configuration.
    
    Priority order:
    1. GitHub API storage (if GITHUB_TOKEN exists)
    2. Local file storage (default)
    
    Default GitHub repo: dn-scribe/nebenchat-data (branch: main)
    """
    # Check for GitHub token
    github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GIT_STORAGE_TOKEN")
    
    if github_token:
        # Use GitHub API storage with defaults
        owner = os.environ.get("GITHUB_REPO_OWNER", "dn-scribe")
        repo = os.environ.get("GITHUB_REPO_NAME", "nebenchat-data")
        branch = os.environ.get("GITHUB_REPO_BRANCH", "main")
        
        return GitHubAPIFileStorage(owner=owner, repo=repo, branch=branch, token=github_token)
    
    # Default to local storage
    return LocalFileStorage()