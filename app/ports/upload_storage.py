from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Protocol


class UploadedContent(Protocol):
    """Framework-independent readable upload."""

    filename: str | None

    async def read(self, size: int = -1) -> bytes: ...


class UploadStorage(Protocol):
    """Bounded staging with cleanup on success, failure, or cancellation."""

    def stage(
        self, upload: UploadedContent, suffix: str, limit: int
    ) -> AbstractAsyncContextManager[Path]: ...

    async def read(self, upload: UploadedContent, limit: int) -> bytes: ...
