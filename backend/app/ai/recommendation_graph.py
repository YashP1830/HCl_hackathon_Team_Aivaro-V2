"""LangGraph wrapper for the existing catalogue-grounded recommendation service.

This keeps response shape and the DB as source of truth while giving the app a
single graph entry point for its AI recommendation operation.
"""
from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.ai.recommendations import recommend_books


class RecommendationState(TypedDict, total=False):
    query: str
    top_k: int
    response: Any


def build_recommendation_graph(db: Session):
    def recommend_node(state: RecommendationState) -> RecommendationState:
        response = recommend_books(db, state["query"], top_k=state.get("top_k", 5))
        # Keep transport output serializable and aligned with the current API schema.
        return {"response": response.model_dump()}

    graph = StateGraph(RecommendationState)
    graph.add_node("recommend", recommend_node)
    graph.set_entry_point("recommend")
    graph.add_edge("recommend", END)
    return graph.compile()


def recommend_via_graph(db: Session, query: str, top_k: int = 5) -> dict:
    result = build_recommendation_graph(db).invoke({"query": query, "top_k": top_k})
    return result["response"]
