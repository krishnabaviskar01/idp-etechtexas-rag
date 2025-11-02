"""LangGraph node implementations for chat workflow."""

from __future__ import annotations

import asyncio
import json
from langchain_core.messages.base import BaseMessage
from pathlib import Path
from typing import Any, Dict, List, Optional
def _preview(text: str, length: int = 120) -> str:
    text = (text or "").replace("\n", " ")
    return text if len(text) <= length else f"{text[:length]}…"


from loguru import logger
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings
from app.services.pinecone_service import (
    PineconeServiceError,
    RetrievedChunk,
    assemble_document_context,
    build_qna_context,
    build_summary_context,
    fetch_full_document_chunks,
    query_context,
)


PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _require_setting(value: Optional[str], name: str) -> str:
    if not value:
        raise ValueError(f"Missing required configuration: {name}")
    return value


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


DECIDE_PROMPT = _load_prompt("decide_next_step.txt")
QNA_PROMPT = _load_prompt("qna.txt")
SUMMARY_PROMPT = _load_prompt("summarization.txt")


# LLM clients
_openai_llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2,
    api_key=_require_setting(settings.OPENAI_API_KEY, "OPENAI_API_KEY"),
    timeout=settings.LLM_TIMEOUT,
    max_retries=settings.LLM_MAX_RETRIES,
)

_google_api_key = _require_setting(settings.GOOGLE_API_KEY, "GOOGLE_API_KEY")

_gemini_router_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",
    temperature=0.1,
    google_api_key=_google_api_key,
)

_gemini_summary_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",
    temperature=0.3,
    google_api_key=_google_api_key,
)


def _latest_human_text(messages: List[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content)
    return ""


def _append_ai_message(messages: List[BaseMessage], content: str) -> List[BaseMessage]:
    updated = list(messages)
    updated.append(AIMessage(content=content))
    return updated


def _truncate(text: str, limit: int = 1500) -> str:
    text = text or ""
    return text if len(text) <= limit else f"{text[:limit]}…"


def _chunk_snapshot(chunks: List[Any], limit: int = 3) -> List[Dict[str, Any]]:
    snapshot: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(chunks[:limit], start=1):
        if hasattr(chunk, "metadata"):
            metadata = getattr(chunk, "metadata") or {}
            text_value = getattr(chunk, "text", "")
            score_value = getattr(chunk, "score", 0.0)
        else:
            metadata = chunk.get("metadata") or {}
            text_value = chunk.get("text") or metadata.get("text") or ""
            score_value = chunk.get("score") or 0.0
        snapshot.append({
            "rank": idx,
            "score": round(score_value if isinstance(score_value, (int, float)) else 0.0, 4),
            "source_file": metadata.get("source_file"),
            "page_index": metadata.get("page_index"),
            "chunk_index": metadata.get("chunk_index"),
            "text_preview": _preview(text_value or metadata.get("text") or "", 200),
        })
    return snapshot


def _snapshot_json(snapshot: List[Dict[str, Any]]) -> str:
    if not snapshot:
        return "[]"
    return json.dumps(snapshot, ensure_ascii=False, indent=2)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _document_sort_key(chunk: RetrievedChunk) -> tuple[int, int]:
    metadata = chunk.metadata or {}
    return (
        _safe_int(metadata.get("page_index"), default=1_000_000),
        _safe_int(metadata.get("chunk_index"), default=1_000_000),
    )


async def decide_next_step(state: Dict[str, Any]) -> Dict[str, Any]:
    messages: List[BaseMessage] = state.get("messages", []) or []
    user_text = _latest_human_text(messages)

    logger.debug("Routing decision received", user_message=_preview(user_text))

    prompt = DECIDE_PROMPT.format(question=user_text)

    try:
        response = await _gemini_router_llm.ainvoke([HumanMessage(content=prompt)])
        decision = (response.content or "").strip().lower()
        if decision not in {"qna", "summarize"}:
            logger.warning(f"Router produced unexpected decision '{decision}'. Defaulting to 'qna'.")
            decision = "qna"
        logger.info("Routing decision completed", decision=decision)
        return {"next_step": decision}
    except Exception as exc:  # pragma: no cover - routing safety net
        logger.error(f"Routing failure: {exc}")
        return {
            "next_step": "qna",
            "error": "Unable to determine next step. Defaulting to question answering.",
        }


async def question_answering_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    messages: List[BaseMessage] = state.get("messages", []) or []
    dataset_name: Optional[str] = state.get("dataset_name")
    user_question = _latest_human_text(messages)

    logger.info(
        "Starting QnA agent",
        question=_preview(user_question),
        dataset=dataset_name,
    )

    error_message: Optional[str] = None
    retrieved_chunks: List[RetrievedChunk] = []
    citation_map: List[Dict[str, Any]] = []

    try:
        retrieved_chunks = await query_context(
            query=user_question,
            top_k=settings.RAG_TOP_K,
            dataset_name=dataset_name,
        )
        snapshot = _chunk_snapshot(retrieved_chunks)
        logger.info(
            "QnA context retrieved ({} chunks) for dataset '{}':\n{}",
            len(retrieved_chunks),
            dataset_name or "default",
            _snapshot_json(snapshot),
        )
    except PineconeServiceError as exc:
        error_message = str(exc)
        logger.error(f"Pinecone retrieval failed for QnA: {exc}")
    except Exception as exc:  # pragma: no cover - safety net
        error_message = "Context retrieval failed. Proceeding without context."
        logger.error(f"Unexpected QnA retrieval error: {exc}")

    context_text, citation_map = build_qna_context(retrieved_chunks)
    if not context_text:
        context_text = "Context unavailable or insufficient."

    prompt = QNA_PROMPT.format(question=user_question, context=context_text)
    logger.info(
        "QnA prompt constructed:\n{}",
        _truncate(prompt, 4000),
    )
    if citation_map:
        logger.info(
            "QnA citations map:\n{}",
            json.dumps(citation_map, ensure_ascii=False, indent=2),
        )

    try:
        response = await _openai_llm.ainvoke([HumanMessage(content=prompt)])
        answer = (response.content or "").strip()
        if not answer:
            answer = "I'm not sure based on the available information."
        logger.info(
            "QnA agent completed",
            answer_preview=_preview(answer),
            context_chunks=len(retrieved_chunks),
        )
    except Exception as exc:  # pragma: no cover - safety net
        logger.error(f"QnA generation failed: {exc}")
        answer = "I'm sorry, I couldn't generate an answer right now."
        error_message = error_message or "Answer generation failed."

    updated_messages = _append_ai_message(messages, answer)

    result: Dict[str, Any] = {
        "answer": answer,
        "messages": updated_messages,
        "context_chunks": len(retrieved_chunks),
    }
    if citation_map:
        result["citations"] = citation_map
    if error_message:
        result["error"] = error_message
    return result


async def summary_generation_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    messages: List[BaseMessage] = state.get("messages", []) or []
    dataset_name: Optional[str] = state.get("dataset_name")
    user_text = _latest_human_text(messages)

    logger.info(
        "Starting summarization agent",
        text_preview=_preview(user_text),
        dataset=dataset_name,
    )

    error_message: Optional[str] = None
    context_chunks: List[RetrievedChunk] = []

    truncation_applied = False
    context_text = ""
    context_chunk_count = 0

    try:
        if settings.SUMMARY_FULL_DOCUMENT_MODE:
            initial_chunks = await query_context(
                query=user_text,
                top_k=1,
                dataset_name=dataset_name,
            )
            initial_snapshot = _chunk_snapshot(initial_chunks, limit=1)
            logger.info(
                "Summarization top-1 retrieval ({} chunk) for dataset '{}':\n{}",
                len(initial_chunks),
                dataset_name or "default",
                _snapshot_json(initial_snapshot),
            )

            if initial_chunks:
                best_chunk = initial_chunks[0]
                metadata = best_chunk.metadata or {}
                document_id = metadata.get("document_id")
                source_file = metadata.get("source_file")
                logger.info(
                    "Summarization document target identified",
                    document_id=document_id,
                    source_file=source_file,
                    dataset=dataset_name,
                )

                full_chunks = await asyncio.to_thread(
                    fetch_full_document_chunks,
                    document_id=document_id,
                    source_file=source_file,
                    dataset_name=dataset_name,
                )

                if full_chunks:
                    context_chunks = sorted(full_chunks, key=_document_sort_key)
                    context_chunk_count = len(context_chunks)
                    context_text, truncation_applied = assemble_document_context(
                        context_chunks,
                        max_chars=settings.SUMMARY_MAX_CONTEXT_CHARS,
                    )
                    if truncation_applied:
                        logger.warning(
                            "Summarization context truncated",
                            document_id=document_id,
                            source_file=source_file,
                            max_chars=settings.SUMMARY_MAX_CONTEXT_CHARS,
                        )
                    logger.info(
                        "Summarization full document fetched",
                        document_id=document_id,
                        source_file=source_file,
                        total_chunks=context_chunk_count,
                    )
                    logger.info(
                        "Summarization context preview:\n{}",
                        _preview(context_text, 2000),
                    )
                else:
                    logger.warning(
                        "Full document retrieval returned no chunks",
                        document_id=document_id,
                        source_file=source_file,
                        dataset=dataset_name,
                    )

        if not context_text:
            if not settings.SUMMARY_FULL_DOCUMENT_MODE:
                context_chunks = await query_context(
                    query=user_text,
                    top_k=settings.RAG_TOP_K,
                    dataset_name=dataset_name,
                )
                snapshot = _chunk_snapshot(context_chunks)
                logger.info(
                    "Summarization context retrieved ({} chunks) for dataset '{}':\n{}",
                    len(context_chunks),
                    dataset_name or "default",
                    _snapshot_json(snapshot),
                )
                context_text = build_summary_context(context_chunks)
                context_chunk_count = len(context_chunks)
            else:
                context_text = "Context unavailable or insufficient."
                context_chunk_count = 0
    except PineconeServiceError as exc:
        error_message = str(exc)
        logger.error(f"Pinecone retrieval failed for summarization: {exc}")
        context_text = "Context unavailable or insufficient."
    except Exception as exc:  # pragma: no cover - safety net
        error_message = "Context retrieval failed. Proceeding without context."
        logger.error(f"Unexpected summarization retrieval error: {exc}")
        context_text = "Context unavailable or insufficient."

    if not context_text:
        context_text = "Context unavailable or insufficient."

    prompt = SUMMARY_PROMPT.format(text=user_text, context=context_text)
    logger.info(
        f"Summarization prompt constructed:\n{prompt}",
    )

    try:
        response = await _gemini_summary_llm.ainvoke([HumanMessage(content=prompt)])
        summary = (response.content or "").strip()
        if not summary:
            summary = "I was unable to create a summary with the available information."
        logger.info(
            "Summarization agent completed",
            summary_preview=_preview(summary),
            context_chunks=context_chunk_count,
        )
    except Exception as exc:  # pragma: no cover - safety net
        logger.error(f"Summarization generation failed: {exc}")
        summary = "I'm sorry, I couldn't generate a summary right now."
        error_message = error_message or "Summary generation failed."

    updated_messages = _append_ai_message(messages, summary)

    result: Dict[str, Any] = {
        "summary": summary,
        "messages": updated_messages,
        "context_chunks": context_chunk_count,
    }
    if error_message:
        result["error"] = error_message
    return result


