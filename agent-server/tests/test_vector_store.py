from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from db.vector_store import ClinicalVectorStore, SIMILARITY_THRESHOLD


@pytest.fixture
def mock_chroma():
    with patch("db.vector_store.chromadb.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_client_cls.return_value = mock_client
        yield mock_client, mock_collection


@pytest.fixture
def store(mock_chroma):
    _mock_client, mock_collection = mock_chroma
    mock_collection.count.return_value = 5
    s = ClinicalVectorStore()
    s._collection = mock_collection
    s._ready = True
    return s


def test_ensure_indexed_creates_collection(mock_chroma):
    mock_client, mock_collection = mock_chroma
    mock_collection.count.return_value = 5

    store = ClinicalVectorStore()
    result = store._ensure_indexed()

    assert result is mock_collection
    assert store._ready is True


def test_ensure_indexed_indexes_when_empty(mock_chroma):
    mock_client, mock_collection = mock_chroma
    mock_collection.count.return_value = 0

    store = ClinicalVectorStore()
    with patch("db.vector_store.KNOWLEDGE_DIR") as mock_dir:
        mock_dir.glob.return_value = []
        result = store._ensure_indexed()

    assert result is mock_collection
    mock_collection.add.assert_not_called()
    assert store._ready is True


def test_ensure_indexed_returns_none_on_error(mock_chroma):
    mock_client, mock_collection = mock_chroma
    mock_collection.count.side_effect = Exception("chroma down")

    store = ClinicalVectorStore()
    result = store._ensure_indexed()

    assert result is None
    assert store._ready is False


def test_query_returns_hits_above_threshold(store):
    mock_collection = store._collection
    mock_collection.count.return_value = 10
    mock_collection.query.return_value = {
        "documents": [["Codeine risk for UMs is high.", "Alternative: morphine."]],
        "metadatas": [
            [{"source": "cpic_opioid.md", "chunk_id": "1"}, {"source": "cpic_opioid.md", "chunk_id": "2"}]
        ],
        "distances": [[0.15, 0.25]],
    }

    results = store.query("codeine")

    assert len(results) == 2
    assert results[0]["similarity"] == 0.85
    assert results[1]["similarity"] == 0.75
    assert results[0]["source"] == "cpic_opioid.md"
    assert results[1]["chunk_id"] == "2"


def test_query_filters_below_threshold(store):
    mock_collection = store._collection
    mock_collection.count.return_value = 10
    mock_collection.query.return_value = {
        "documents": [["Irrelevant text about metabolism."]],
        "metadatas": [[{"source": "other.md", "chunk_id": "1"}]],
        "distances": [[0.85]],
    }

    results = store.query("codeine")

    assert len(results) == 0


def test_query_mixed_threshold(store):
    mock_collection = store._collection
    mock_collection.count.return_value = 10
    mock_collection.query.return_value = {
        "documents": [["Good match.", "Bad match.", "Okay match."]],
        "metadatas": [
            [
                {"source": "a.md", "chunk_id": "1"},
                {"source": "b.md", "chunk_id": "2"},
                {"source": "c.md", "chunk_id": "3"},
            ]
        ],
        "distances": [[0.1, 0.9, 0.6]],
    }

    results = store.query("codeine")

    assert len(results) == 2
    assert results[0]["similarity"] == 0.9
    assert results[1]["similarity"] == 0.4
    assert results[0]["source"] == "a.md"
    assert results[1]["source"] == "c.md"


def test_query_returns_empty_when_collection_unavailable(mock_chroma):
    mock_client, mock_collection = mock_chroma
    mock_collection.count.side_effect = Exception("chroma down")

    store = ClinicalVectorStore()
    results = store.query("anything")

    assert results == []


def test_query_returns_empty_on_query_exception(store):
    mock_collection = store._collection
    mock_collection.count.return_value = 10
    mock_collection.query.side_effect = Exception("query failed")

    results = store.query("codeine")

    assert results == []


def test_query_empty_results_dict(store):
    mock_collection = store._collection
    mock_collection.count.return_value = 10
    mock_collection.query.return_value = {
        "documents": [],
        "metadatas": [],
        "distances": [],
    }

    results = store.query("codeine")
    assert results == []


def test_query_top_k_respected(store):
    mock_collection = store._collection
    mock_collection.count.return_value = 10

    store.query("codeine", top_k=3)

    mock_collection.query.assert_called_once()
    _call_kwargs = mock_collection.query.call_args[1]
    assert _call_kwargs["n_results"] == 3


def test_query_top_k_capped_by_count(store):
    mock_collection = store._collection
    mock_collection.count.return_value = 2

    store.query("codeine", top_k=5)

    mock_collection.query.assert_called_once()
    _call_kwargs = mock_collection.query.call_args[1]
    assert _call_kwargs["n_results"] == 2


def test_query_clinical_knowledge_respects_min_similarity(store):
    from db.vector_store import get_store, query_clinical_knowledge

    global_store = get_store()
    mock_collection = store._collection
    mock_collection.count.return_value = 10
    mock_collection.query.return_value = {
        "documents": [["Hit one.", "Hit two."]],
        "metadatas": [
            [{"source": "a.md", "chunk_id": "1"}, {"source": "b.md", "chunk_id": "2"}]
        ],
        "distances": [[0.1, 0.8]],
    }
    saved_ready = global_store._ready
    saved_collection = global_store._collection
    global_store._collection = mock_collection
    global_store._ready = True

    results = query_clinical_knowledge("codeine", min_similarity=0.5)

    global_store._ready = saved_ready
    global_store._collection = saved_collection

    assert len(results) == 1
    assert results[0]["similarity"] == 0.9


def test_global_store_singleton(mock_chroma):
    from db.vector_store import get_store

    s1 = get_store()
    s2 = get_store()

    assert s1 is s2


def test_index_files_chunks_correctly(mock_chroma):
    mock_client, mock_collection = mock_chroma
    mock_collection.count.return_value = 0

    fake_md = "# Header\n\n## Section 1\nContent one.\n\n## Section 2\nContent two."
    with patch("db.vector_store.KNOWLEDGE_DIR") as mock_dir:
        mock_file = MagicMock()
        mock_file.read_text.return_value = fake_md
        mock_file.name = "test_knowledge.md"
        mock_dir.glob.return_value = [mock_file]

        store = ClinicalVectorStore()
        store._collection = mock_collection
        store._index_files()

        mock_collection.add.assert_called_once()
        _call_kwargs = mock_collection.add.call_args[1]
        assert len(_call_kwargs["documents"]) == 3
        assert _call_kwargs["ids"] == [
            "test_knowledge.md:1",
            "test_knowledge.md:2",
            "test_knowledge.md:3",
        ]
        assert _call_kwargs["metadatas"][0]["source"] == "test_knowledge.md"
