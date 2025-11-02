"""Chat router exposing the LangGraph workflow endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from loguru import logger
from langchain_core.messages import HumanMessage

from app.schemas.chat import ChatRequest, ChatResponse


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest, request: Request) -> ChatResponse:
    """Route chat messages through the LangGraph workflow."""

    logger.info(
        "Received chat request",
        message_preview=payload.message[:200],
        dataset=payload.dataset_name,
    )

    chat_graph = getattr(request.app.state, "chat_graph", None)
    if chat_graph is None:
        raise HTTPException(status_code=503, detail="Chat workflow is not available")

    if not payload.message:
        raise HTTPException(status_code=422, detail="Message is required")

    initial_state = {
        "messages": [HumanMessage(content=payload.message)],
    }
    if payload.dataset_name:
        initial_state["dataset_name"] = payload.dataset_name

    result = await chat_graph.ainvoke(initial_state)

    logger.debug(
        "Chat graph execution completed",
        context_chunks=result.get("context_chunks"),
        keys=list(result.keys()),
    )

    context_chunks = result.get("context_chunks", 0)

    if answer := result.get("answer"):
        response = ChatResponse(type="qna", answer=answer, context_chunks=context_chunks)
        if error := result.get("error"):
            response.error = error
        if citations := result.get("citations"):
            response.citations = citations
        logger.info("Chat response generated", response_type="qna", context_chunks=context_chunks)
        return response

    if summary := result.get("summary"):
        response = ChatResponse(type="summary", summary=summary, context_chunks=context_chunks)
        if error := result.get("error"):
            response.error = error
        if citations := result.get("citations"):
            response.citations = citations
        logger.info("Chat response generated", response_type="summary", context_chunks=context_chunks)
        return response

    if error := result.get("error"):
        logger.warning("Chat response returned error", error=error)
        return ChatResponse(type="error", error=error)

    logger.warning("Chat response type unknown", state_keys=list(result.keys()))
    return ChatResponse(type="unknown", state=result)


