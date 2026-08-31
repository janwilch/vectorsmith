from __future__ import annotations

import pytest

from vectorsmith_core.adapters.base import SearchRequest
from vectorsmith_core.adapters.chroma import ChromaAdapter, _chroma_rows


def test_chroma_rows_include_document_content() -> None:
    rows = _chroma_rows(
        {
            "ids": [["a1"]],
            "metadatas": [[{"file_path": "x.md"}]],
            "documents": [["hello world"]],
            "distances": [[0.42]],
        }
    )
    assert rows == [
        {"_id": "a1", "file_path": "x.md", "content": "hello world", "_score": 0.42}
    ]


@pytest.mark.asyncio
async def test_chroma_search_requests_documents() -> None:
    includes: list[list[str]] = []

    class FakeCollection:
        async def get(self, *, where, limit, include):  # noqa: ANN001
            includes.append(include)
            return {
                "ids": ["a1"],
                "metadatas": [{"file_path": "x.md"}],
                "documents": ["hello world"],
            }

        async def query(self, *, query_embeddings, n_results, where, include):  # noqa: ANN001
            includes.append(include)
            return {
                "ids": [["a1"]],
                "metadatas": [[{"file_path": "x.md"}]],
                "documents": [["hello world"]],
                "distances": [[0.42]],
            }

    class FakeClient:
        async def get_collection(self, _name: str) -> FakeCollection:
            return FakeCollection()

    adapter = ChromaAdapter(url="http://localhost:8000")

    async def fake_sdk() -> FakeClient:
        return FakeClient()

    adapter._sdk = fake_sdk  # type: ignore[method-assign]

    get_rows = await adapter.search(SearchRequest(collection="docs", limit=1))
    query_rows = await adapter.search(
        SearchRequest(collection="docs", vector=[0.1], limit=1)
    )

    assert includes == [
        ["metadatas", "documents"],
        ["metadatas", "documents", "distances"],
    ]
    assert get_rows.rows[0]["content"] == "hello world"
    assert query_rows.rows[0]["content"] == "hello world"
