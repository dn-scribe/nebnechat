import abc
from typing import Any, List, Optional


class FileStorage(abc.ABC):
    @abc.abstractmethod
    def read(self, path: str, mode: str = "r", encoding: Optional[str] = None) -> Any:
        """Read the contents of a file."""
        pass

    @abc.abstractmethod
    def write(self, path: str, data: Any, mode: str = "w", encoding: Optional[str] = None) -> None:
        """Write data to a file."""
        pass

    @abc.abstractmethod
    def remove(self, path: str) -> None:
        """Remove a file."""
        pass

    @abc.abstractmethod
    def exists(self, path: str) -> bool:
        """Check if a file exists."""
        pass

    @abc.abstractmethod
    def makedirs(self, path: str, exist_ok: bool = True) -> None:
        """Create directories recursively."""
        pass

    @abc.abstractmethod
    def listdir(self, path: str) -> List[str]:
        """List files in a directory."""
        pass