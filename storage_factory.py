import os
from typing import Optional
from local_storage import LocalFileStorage
from git_storage import GitFileStorage
from storage import FileStorage

def get_storage() -> FileStorage:
    git_url = os.environ.get("GIT_STORAGE")
    if git_url:
        # Optionally, parse branch from URL or env if needed
        return GitFileStorage(git_url)
    else:
        return LocalFileStorage()