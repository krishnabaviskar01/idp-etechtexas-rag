"""LangGraph chat flow definition."""

from __future__ import annotations

from typing import List, Literal, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import END, StateGraph

from app.langgraph.chat_nodes import (
    decide_next_step,
    question_answering_agent,
    summary_generation_agent,
)


class ChatState(TypedDict, total=False):
    messages: List[BaseMessage]
    next_step: Literal["qna", "summarize"]
    answer: str
    summary: str
    error: str
    dataset_name: Optional[str]
    context_chunks: int


def _route_next_step(state: ChatState) -> str:
    next_step = state.get("next_step", "qna")
    if next_step not in {"qna", "summarize"}:
        return "qna"
    return next_step


def build_chat_graph():
    """Compile and return the chat workflow graph."""

    graph = StateGraph(ChatState)

    graph.add_node("decide_next_step", decide_next_step)
    graph.add_node("question_answering_agent", question_answering_agent)
    graph.add_node("summary_generation_agent", summary_generation_agent)

    graph.set_entry_point("decide_next_step")

    graph.add_conditional_edges(
        "decide_next_step",
        _route_next_step,
        {
            "qna": "question_answering_agent",
            "summarize": "summary_generation_agent",
        },
    )

    graph.add_edge("question_answering_agent", END)
    graph.add_edge("summary_generation_agent", END)

    return graph.compile()


