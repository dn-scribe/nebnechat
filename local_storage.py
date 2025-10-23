import os
from typing import Any, List, Optional
from storage import FileStorage

class LocalFileStorage(FileStorage):
    def read(self, path: str, mode: str = "r", encoding: Optional[str] = None) -> Any:
        with open(path, mode, encoding=encoding) as f:
            return f.read()

    def write(self, path: str, data: Any, mode: str = "w", encoding: Optional[str] = None) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode, encoding=encoding) as f:
            f.write(data)

    def remove(self, path: str) -> None:
        if os.path.exists(path):
            os.remove(path)

    def exists(self, path: str) -> bool:
        return os.path.exists(path)

    def makedirs(self, path: str, exist_ok: bool = True) -> None:
        os.makedirs(path, exist_ok=exist_ok)

    def listdir(self, path: str) -> List[str]:
        return os.listdir(path)