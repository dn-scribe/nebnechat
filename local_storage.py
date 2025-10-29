import os
from typing import Any, List, Optional
from storage import FileStorage

class LocalFileStorage(FileStorage):
    def _validate_path(self, path: str):
        if not isinstance(path, str) or not path.strip():
            import logging
            logging.error(f"LocalFileStorage: Invalid file path: '{path}'")
            raise ValueError(f"Invalid file path: '{path}'")

    def read(self, path: str, mode: str = "r", encoding: Optional[str] = None) -> Any:
        self._validate_path(path)
        with open(path, mode, encoding=encoding) as f:
            return f.read()

    def write(self, path: str, data: Any, mode: str = "w", encoding: Optional[str] = None) -> None:
        self._validate_path(path)
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(path, mode, encoding=encoding) as f:
            f.write(data)

    def remove(self, path: str) -> None:
        self._validate_path(path)
        if os.path.exists(path):
            os.remove(path)

    def exists(self, path: str) -> bool:
        self._validate_path(path)
        return os.path.exists(path)

    def makedirs(self, path: str, exist_ok: bool = True) -> None:
        self._validate_path(path)
        os.makedirs(path, exist_ok=exist_ok)

    def listdir(self, path: str) -> List[str]:
        self._validate_path(path)
        return os.listdir(path)