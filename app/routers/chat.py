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

    answer = result.get("answer")
    response_type = "qna"

    if not answer and (summary := result.get("summary")):
        answer = summary
        response_type = "summary"

    if answer:
        response = ChatResponse(
            type=response_type,
            answer=answer,
            context_chunks=context_chunks,
            citations=result.get("citations"),
        )
        logger.info("Chat response generated", response_type=response_type, context_chunks=context_chunks)
        return response

    if error := result.get("error"):
        logger.warning("Chat response returned error", error=error)
        return ChatResponse(type="error", answer=error)

    logger.warning("Chat response type unknown", state_keys=list(result.keys()))
    return ChatResponse(type="unknown", answer="Unable to generate a response.")


