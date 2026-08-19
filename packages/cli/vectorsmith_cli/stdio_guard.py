"""Keep stdout reserved for the MCP protocol."""

from __future__ import annotations

import logging
import sys
import warnings


class _StdoutGuard:
    def __init__(self, real: object) -> None:
        self._real = real

    def write(self, data: str) -> int:
        if data and data.strip():
            warnings.warn("write to stdout intercepted; use stderr", RuntimeWarning, stacklevel=2)
            sys.stderr.write(data)
            return len(data)
        return 0

    def flush(self) -> None:
        sys.stderr.flush()

    def fileno(self) -> int:
        return sys.stderr.fileno()


def install() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, force=True)
    for name in (
        "httpx",
        "qdrant_client",
        "chromadb",
        "onnxruntime",
        "pinecone",
        "weaviate",
        "pymilvus",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)
    # transport keeps the real stdout; everything else is guarded after serve starts
    sys.stdout = _StdoutGuard(sys.stdout)  # type: ignore[assignment]
