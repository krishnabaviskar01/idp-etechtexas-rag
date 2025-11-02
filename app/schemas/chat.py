"""Schemas for chat endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message to process")
    dataset_name: Optional[str] = Field(
        default=None,
        description="Optional dataset namespace to scope retrieval",
    )


class ChatResponse(BaseModel):
    type: Literal["qna", "summary", "error", "unknown"]
    answer: Optional[str] = None
    summary: Optional[str] = None
    error: Optional[str] = None
    context_chunks: Optional[int] = None
    state: Optional[Dict[str, Any]] = None
    citations: Optional[List[Dict[str, Any]]] = None


