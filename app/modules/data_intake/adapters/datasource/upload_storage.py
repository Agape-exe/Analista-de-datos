import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from app.modules.data_intake.ports.upload_storage import UploadedContent
from app.shared.application.errors import UploadTooLargeError


class TemporaryUploadStorage:
    """Stage generated paths; a zero dataset limit allows uploads of any size."""

    def __init__(self, chunk_size: int, directory: Path | None = None) -> None:
        self.chunk_size = chunk_size
        self.directory = directory

    @asynccontextmanager
    async def stage(self, upload: UploadedContent, suffix: str, limit: int) -> AsyncIterator[Path]:
        with TemporaryDirectory(prefix="analyst-intake-", dir=self.directory) as directory:
            path = Path(directory) / f"dataset{suffix}"
            size = 0
            with path.open("wb") as stream:
                while chunk := await upload.read(self.chunk_size):
                    size += len(chunk)
                    if limit > 0 and size > limit:
                        raise UploadTooLargeError(f"Dataset exceeds the {limit}-byte upload limit")
                    await asyncio.to_thread(stream.write, chunk)
            yield path

    async def read(self, upload: UploadedContent, limit: int) -> bytes:
        chunks: list[bytes] = []
        size = 0
        while chunk := await upload.read(self.chunk_size):
            size += len(chunk)
            if size > limit:
                raise UploadTooLargeError(f"Dictionary exceeds the {limit}-byte upload limit")
            chunks.append(chunk)
        return b"".join(chunks)
