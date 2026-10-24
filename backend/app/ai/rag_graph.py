"""LangGraph RAG workflow for answering questions from the book catalogue."""
from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.ai.embeddings import get_embeddings
from app.ai.llm import get_llm
from app.ai.vector_store import search_books
from app.repositories import repositories as repo

logger = logging.getLogger("app.ai.rag_graph")


class RagState(TypedDict, total=False):
    question: str
    top_k: int
    context: list[dict[str, Any]]
    best_score: float
    answer: str
    sources: list[dict[str, str]]
    status: str


def build_rag_graph(db: Session):
    """retrieve -> grade -> grounded generation or not-found fallback."""
    def retrieve(state: RagState) -> RagState:
        question = state["question"].strip()
        if not question:
            return {"context": [], "best_score": 0.0}
        vector = get_embeddings().embed(question)
        hits = search_books(db, vector, top_k=max(1, min(state.get("top_k", 4), 10)), min_score=0.12)
        context: list[dict[str, Any]] = []
        for hit in hits:
            book = repo.get_book(db, hit.book_id)
            if book is not None:
                context.append({"id": str(book.id), "title": book.title, "author": book.author,
                    "description": book.description or "", "genre": book.genre or "",
                    "publisher": book.publisher or "", "score": float(hit.score)})
        return {"context": context, "best_score": max((x["score"] for x in context), default=0.0)}

    def grade(state: RagState) -> str:
        return "generate" if state.get("context") and state.get("best_score", 0.0) >= 0.12 else "not_found"

    def generate(state: RagState) -> RagState:
        context_json = json.dumps(state.get("context", []), ensure_ascii=False)
        system = ("You are the library's RAG assistant. Answer only from the supplied context. "
            "If the context does not contain the answer, say you cannot determine it. "
            "Never invent book details, stock, policies, or citations. Keep the answer concise.")
        user = f"Question: {state['question']}\nCatalogue context (JSON):\n{context_json}"
        answer = get_llm().complete(system, user, temperature=0.1).strip()
        return {"answer": answer, "status": "answered" if answer else "not_found",
            "sources": [{"book_id": str(x["id"]), "title": str(x["title"])} for x in state.get("context", [])]}

    def not_found(state: RagState) -> RagState:
        return {"answer": "I couldn't find enough relevant information in the library catalogue to answer that confidently.",
            "status": "not_found", "sources": []}

    graph = StateGraph(RagState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_node("not_found", not_found)
    graph.set_entry_point("retrieve")
    graph.add_conditional_edges("retrieve", grade, {"generate": "generate", "not_found": "not_found"})
    graph.add_edge("generate", END)
    graph.add_edge("not_found", END)
    return graph.compile()


def answer_from_catalog(db: Session, question: str, top_k: int = 4) -> dict[str, Any]:
    """Run the graph and return JSON-friendly response data."""
    try:
        output = build_rag_graph(db).invoke({"question": question, "top_k": top_k})
        return {"answer": output.get("answer", ""), "status": output.get("status", "not_found"), "sources": output.get("sources", [])}
    except Exception:
        logger.exception("RAG graph failed")
        return {"answer": "The library assistant encountered an error while searching the catalogue. Please try again.",
            "status": "error", "sources": []}
