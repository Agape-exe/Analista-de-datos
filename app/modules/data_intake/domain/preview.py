"""Fixed safety ceilings for the read-only preview contract (not upload limits)."""

import json

PreviewValue = str | int | float | bool | None

DEFAULT_PREVIEW_LIMIT = 20
MAX_PREVIEW_LIMIT = 100
MAX_PREVIEW_OFFSET = 2**53 - 1
MAX_PREVIEW_COLUMNS = 1_000
MAX_PREVIEW_CELLS = 10_000
MAX_PREVIEW_BYTES = 1_048_576
MAX_PREVIEW_VALUE_BYTES = 65_536


class PreviewTooLargeError(Exception):
    """The requested page exceeds a documented resource ceiling."""


class PreviewUnsupportedError(Exception):
    """The local table or a value cannot be represented safely as a preview."""


def preview_value_size(value: PreviewValue) -> int:
    """Count JSON UTF-8 bytes without encoding an unbounded string or integer."""
    if isinstance(value, str) and len(value) > MAX_PREVIEW_VALUE_BYTES:
        raise PreviewTooLargeError
    if isinstance(value, int) and value.bit_length() > MAX_PREVIEW_VALUE_BYTES:
        raise PreviewTooLargeError
    try:
        size = len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (ValueError, OverflowError, UnicodeError) as error:
        raise PreviewUnsupportedError from error
    if size > MAX_PREVIEW_VALUE_BYTES:
        raise PreviewTooLargeError
    return size
