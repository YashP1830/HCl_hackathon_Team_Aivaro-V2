"""Top-level LangGraph router (KT 6).

A small StateGraph that routes an incoming AI request to the right service
(recommendation / FAQ / research) via a conditional edge, as described in the
knowledge transfer. The individual services keep their own logic; this graph is
the single routing entry point so the AI surface stays coherent.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.ai.faq_graph import answer_faq
from app.ai.recommendations import recommend_books
from app.ai.research import search_research_papers

logger = logging.getLogger("app.ai.router_graph")

_RESEARCH_HINTS = ("paper", "papers", "research", "scholar", "study", "studies", "journal", "citation")
_FAQ_HINTS = ("how do i", "how can i", "where", "what is the", "borrow", "return", "fine", "membership", "hours")


class RouterState(TypedDict, total=False):
    kind: str          # recommend | faq | research
    text: str
    top_k: int
    max_results: int
    result: Any
    route: str


def classify(text: str) -> str:
    t = (text or "").lower()
    if any(h in t for h in _RESEARCH_HINTS):
        return "research"
    if any(h in t for h in _FAQ_HINTS) or t.strip().endswith("?"):
        return "faq"
    return "recommend"


def build_router(db: Session):
    def route_edge(state: RouterState) -> str:
        return state.get("kind") or classify(state.get("text", ""))

    def recommend_node(state: RouterState) -> RouterState:
        res = recommend_books(db, state["text"], top_k=state.get("top_k", 5))
        return {"result": res, "route": "recommend"}

    def faq_node(state: RouterState) -> RouterState:
        res = answer_faq(db, state["text"])
        return {"result": res, "route": "faq"}

    def research_node(state: RouterState) -> RouterState:
        res = search_research_papers(state["text"], max_results=state.get("max_results", 5))
        return {"result": res, "route": "research"}

    graph = StateGraph(RouterState)
    graph.add_node("recommend", recommend_node)
    graph.add_node("faq", faq_node)
    graph.add_node("research", research_node)

    # entry is a passthrough that only routes
    graph.add_node("start", lambda s: {})
    graph.set_entry_point("start")
    graph.add_conditional_edges(
        "start",
        route_edge,
        {"recommend": "recommend", "faq": "faq", "research": "research"},
    )
    for node in ("recommend", "faq", "research"):
        graph.add_edge(node, END)
    return graph.compile()


def route_request(db: Session, text: str, kind: Optional[str] = None, top_k: int = 5, max_results: int = 5):
    app = build_router(db)
    state: RouterState = {"text": text, "top_k": top_k, "max_results": max_results}
    if kind:
        state["kind"] = kind
    out = app.invoke(state)
    return out.get("route"), out.get("result")
