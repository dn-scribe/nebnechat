import os
import tempfile
from typing import Any, List, Optional
from storage import FileStorage
from git import Repo, GitCommandError

class GitFileStorage(FileStorage):
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
        return os.path.join(self.local_dir, path.lstrip("/"))

    def read(self, path: str, mode: str = "r", encoding: Optional[str] = None) -> Any:
        full_path = self._full_path(path)
        with open(full_path, mode, encoding=encoding) as f:
            return f.read()

    def write(self, path: str, data: Any, mode: str = "w", encoding: Optional[str] = None) -> None:
        full_path = self._full_path(path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, mode, encoding=encoding) as f:
            f.write(data)
        self.repo.git.add(full_path)
        self.repo.index.commit(f"Update {path}")
        # Always pull before pushing to avoid non-fast-forward errors
        self.repo.git.fetch("origin", self.branch)
        self.repo.git.pull("origin", self.branch)
        self.repo.git.push("origin", self.branch)

    def remove(self, path: str) -> None:
        full_path = self._full_path(path)
        if os.path.exists(full_path):
            os.remove(full_path)
            self.repo.git.add(full_path)
            self.repo.index.commit(f"Remove {path}")
            # Always pull before pushing to avoid non-fast-forward errors
            self.repo.git.fetch("origin", self.branch)
            self.repo.git.pull("origin", self.branch)
            self.repo.git.push("origin", self.branch)

    def exists(self, path: str) -> bool:
        return os.path.exists(self._full_path(path))

    def makedirs(self, path: str, exist_ok: bool = True) -> None:
        os.makedirs(self._full_path(path), exist_ok=exist_ok)
        # Optionally commit directory creation (git tracks files, not empty dirs)

    def listdir(self, path: str) -> List[str]:
        full_path = self._full_path(path)
        return os.listdir(full_path)