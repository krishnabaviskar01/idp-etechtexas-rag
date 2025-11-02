"""Pinecone retrieval service for LangGraph chat workflow."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Tuple

from loguru import logger
from pinecone import Pinecone, PineconeException
from langchain_openai import OpenAIEmbeddings

from app.config import settings


class PineconeServiceError(RuntimeError):
    """Custom error for Pinecone service issues."""


@dataclass
class RetrievedChunk:
    """Structured representation of a Pinecone match."""

    id: Optional[str]
    score: float
    text: str
    metadata: Dict[str, Any]


def _require_env(value: Optional[str], name: str) -> str:
    if not value:
        logger.error("Required configuration missing", setting=name)
        raise PineconeServiceError(f"Missing required setting '{name}'.")
    return value


@lru_cache(maxsize=1)
def get_embeddings() -> OpenAIEmbeddings:
    """Initialize and cache OpenAI embeddings client."""
    api_key = _require_env(settings.OPENAI_API_KEY, "OPENAI_API_KEY")
    logger.debug("Initializing OpenAI embeddings client")
    return OpenAIEmbeddings(
        api_key=api_key,
        model="text-embedding-3-small",
        max_retries=settings.LLM_MAX_RETRIES,
    )


@lru_cache(maxsize=1)
def get_pinecone_client() -> Pinecone:
    """Initialize and cache Pinecone client."""
    api_key = _require_env(settings.PINECONE_API_KEY, "PINECONE_API_KEY")
    environment = settings.PINECONE_ENVIRONMENT
    if environment:
        logger.debug("Initializing Pinecone client with environment", environment=environment)
        return Pinecone(api_key=api_key, environment=environment)
    logger.debug("Initializing Pinecone client without explicit environment")
    return Pinecone(api_key=api_key)


@lru_cache(maxsize=1)
def get_pinecone_index():
    """Get the configured Pinecone index instance."""
    client = get_pinecone_client()
    index_name = _require_env(settings.PINECONE_INDEX_NAME, "PINECONE_INDEX_NAME")
    try:
        logger.debug("Connecting to Pinecone index", index=index_name)
        return client.Index(index_name)
    except PineconeException as exc:
        logger.error(f"Failed to initialize Pinecone index '{index_name}': {exc}")
        raise PineconeServiceError("Unable to initialize Pinecone index. Check configuration and connectivity.") from exc


def _zero_embedding_vector() -> List[float]:
    """Return a reusable zero vector matching the embedding dimension."""

    return [0.0] * settings.EMBEDDING_DIMENSION


async def _embed_query_text(query_text: str) -> List[float]:
    logger.debug("Generating embedding for query", preview=query_text[:120])
    embeddings = get_embeddings()
    embedding = await asyncio.to_thread(embeddings.embed_query, query_text)
    logger.debug("Embedding generated", dimensions=len(embedding))
    return embedding


def _score_from_match(match: Any) -> float:
    """Safely extract a numeric score from a Pinecone match object."""

    score_value = getattr(match, "score", None)
    if score_value is None and isinstance(match, dict):
        score_value = match.get("score")
    try:
        return float(score_value) if score_value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


async def query_context(
    query: str,
    top_k: int | None = None,
    namespace: Optional[str] = None,
    filter: Optional[Dict[str, Any]] = None,
    dataset_name: Optional[str] = None,
) -> List[RetrievedChunk]:
    """Query Pinecone for relevant context chunks and return structured matches."""

    if not query:
        logger.warning("Empty query received for Pinecone retrieval")
        return []

    effective_top_k = top_k or settings.RAG_TOP_K
    filter_payload: Dict[str, Any] = {}
    if filter:
        filter_payload.update(filter)
    if dataset_name:
        filter_payload.setdefault("dataset_name", {"$eq": dataset_name})

    logger.info(
        "Querying Pinecone",
        top_k=effective_top_k,
        namespace=namespace,
        filter=filter_payload or None,
    )

    try:
        vector = await _embed_query_text(query)
    except PineconeServiceError:
        raise
    except Exception as exc:  # pragma: no cover - safety net
        logger.error(f"Failed to generate embedding for query: {exc}")
        raise PineconeServiceError("Unable to generate embedding for query text.") from exc

    try:
        index = get_pinecone_index()
        response = await asyncio.to_thread(
            index.query,
            vector=vector,
            top_k=effective_top_k,
            namespace=namespace,
            include_metadata=True,
            include_values=False,
            filter=filter_payload or None,
        )
    except PineconeServiceError:
        logger.error("Pinecone index initialization failed during query")
        raise
    except Exception as exc:  # pragma: no cover - safety net
        logger.error(f"Pinecone query failed: {exc}")
        raise PineconeServiceError("Pinecone query failed. See logs for details.") from exc

    matches = getattr(response, "matches", None)
    if matches is None and isinstance(response, dict):
        matches = response.get("matches", [])
    matches = matches or []
    logger.debug("Pinecone query returned matches", count=len(matches))
    chunks: List[RetrievedChunk] = []

    sorted_matches = sorted(matches, key=_score_from_match, reverse=True)

    if sorted_matches:
        preview: List[Dict[str, Any]] = []
        for match in sorted_matches[: min(3, len(sorted_matches))]:
            metadata = getattr(match, "metadata", None)
            if metadata is None and isinstance(match, dict):
                metadata = match.get("metadata", {})
            metadata = metadata or {}
            preview.append({
                "id": getattr(match, "id", None)
                if not isinstance(match, dict)
                else match.get("id"),
                "score": round(_score_from_match(match), 4),
                "source_file": metadata.get("source_file"),
                "page_index": metadata.get("page_index"),
                "chunk_index": metadata.get("chunk_index"),
                "text_preview": (metadata.get("text") or "")[:200],
            })
        logger.info(
            "Pinecone top matches preview:\n{}",
            json.dumps(preview, ensure_ascii=False, indent=2),
        )

    for match in sorted_matches:
        metadata = getattr(match, "metadata", None)
        if metadata is None and isinstance(match, dict):
            metadata = match.get("metadata", {})
        metadata = metadata or {}
        text = metadata.get("text") or metadata.get("chunk") or ""
        score = getattr(match, "score", None)
        if score is None and isinstance(match, dict):
            score = match.get("score")
        logger.trace(
            "Pinecone match processed",
            text_preview=text[:120],
            score=score,
            metadata_keys=list(metadata.keys()),
        )
        chunks.append(
            RetrievedChunk(
                id=getattr(match, "id", None)
                if not isinstance(match, dict)
                else match.get("id"),
                score=float(score) if score is not None else 0.0,
                text=text,
                metadata=metadata,
            )
        )

    logger.info("Pinecone retrieval completed", returned=len(chunks))
    return chunks


def fetch_full_document_chunks(
    *,
    document_id: Optional[str],
    source_file: Optional[str],
    dataset_name: Optional[str] = None,
) -> List[RetrievedChunk]:
    """Fetch all chunks for the target document using metadata filters only."""

    if not document_id and not source_file:
        logger.warning("Full document retrieval requested without document identifiers")
        return []

    filter_payload: Dict[str, Any] = {}
    if document_id:
        filter_payload["document_id"] = {"$eq": document_id}
    elif source_file:
        filter_payload["source_file"] = {"$eq": source_file}

    if dataset_name:
        filter_payload["dataset_name"] = {"$eq": dataset_name}

    logger.info(
        "Fetching full document chunks",
        document_id=document_id,
        source_file=source_file,
        dataset=dataset_name,
        filter=filter_payload,
    )

    try:
        index = get_pinecone_index()
        response = index.query(
            id=None,
            vector=_zero_embedding_vector(),
            filter=filter_payload,
            include_metadata=True,
            include_values=False,
            top_k=settings.SUMMARY_DOC_MAX_CHUNKS,
        )
    except Exception as exc:  # pragma: no cover - safety net
        logger.error(f"Failed to fetch full document chunks: {exc}")
        return []

    matches = getattr(response, "matches", None)
    if matches is None and isinstance(response, dict):
        matches = response.get("matches", [])
    matches = matches or []

    logger.info("Full document retrieval raw matches", count=len(matches))

    chunks: List[RetrievedChunk] = []
    for match in matches:
        metadata = getattr(match, "metadata", None)
        if metadata is None and isinstance(match, dict):
            metadata = match.get("metadata", {})
        metadata = metadata or {}
        text = metadata.get("text") or metadata.get("chunk") or ""
        score = getattr(match, "score", None)
        if score is None and isinstance(match, dict):
            score = match.get("score")
        chunks.append(
            RetrievedChunk(
                id=getattr(match, "id", None)
                if not isinstance(match, dict)
                else match.get("id"),
                score=_score_from_match(match),
                text=text,
                metadata=metadata,
            )
        )

    logger.info("Full document retrieval completed", returned=len(chunks))
    return chunks


def assemble_document_context(
    chunks: Iterable[RetrievedChunk],
    *,
    max_chars: Optional[int] = None,
) -> Tuple[str, bool]:
    """Join chunk texts into a single document context string."""

    texts: List[str] = []
    for chunk in chunks:
        text = (chunk.text or "").strip()
        if text:
            texts.append(text)

    combined = "\n\n".join(texts)
    if not max_chars or len(combined) <= max_chars:
        return combined, False

    truncated_text = combined[:max_chars].rstrip()
    if not truncated_text.endswith("…"):
        truncated_text += "…"
    return truncated_text, True


def build_qna_context(chunks: List[RetrievedChunk]) -> Tuple[str, List[Dict[str, Any]]]:
    """Create a labeled context block and citation map similar to the reference script."""

    if not chunks:
        return "", []

    max_context = settings.RAG_MAX_CONTEXT_CHARS
    max_snippet = settings.RAG_MAX_SNIPPET_CHARS

    lines: List[str] = []
    citation_map: List[Dict[str, Any]] = []
    used_len = 0

    for index, chunk in enumerate(chunks, start=1):
        text = (chunk.text or "").strip()
        if not text:
            continue
        if len(text) > max_snippet:
            text = text[:max_snippet] + "…"

        source_file = chunk.metadata.get("source_file")
        header = f"[CIT:{index}] {source_file or 'unknown_file'}"
        block = f"{header}\n{text}\n"

        if used_len + len(block) > max_context:
            break

        lines.append(block)
        citation_map.append(
            {
                "label": index,
                "id": chunk.id,
                "score": round(chunk.score, 4),
                "source_file": source_file,
                "source_url": chunk.metadata.get("source_url"),
                "page_index": chunk.metadata.get("page_index"),
                "chunk_index": chunk.metadata.get("chunk_index"),
                "title": chunk.metadata.get("title"),
                "court_name": chunk.metadata.get("court_name"),
                "case_number": chunk.metadata.get("case_number"),
                "decision_date": chunk.metadata.get("decision_date"),
            }
        )
        used_len += len(block)

    return "\n".join(lines), citation_map


def build_summary_context(
    chunks: List[RetrievedChunk],
    *,
    max_chars: Optional[int] = None,
    max_snippet: Optional[int] = None,
) -> str:
    """Build a concise context string for partial summarization fallback."""

    if not chunks:
        return ""

    max_chars = max_chars or settings.RAG_MAX_CONTEXT_CHARS
    max_snippet = max_snippet or settings.RAG_MAX_SNIPPET_CHARS

    segments: List[str] = []
    used_len = 0

    for chunk in chunks:
        text = (chunk.text or "").strip()
        if not text:
            continue
        snippet = text[:max_snippet] + ("…" if len(text) > max_snippet else "")
        if used_len + len(snippet) > max_chars:
            break
        segments.append(snippet)
        used_len += len(snippet)

    return "\n---\n".join(segments)


