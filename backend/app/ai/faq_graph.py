r"""FAQ chatbot as a real LangGraph StateGraph (KT 6).

Graph:
    retrieve -> grade --(relevant)--> answer -> END
                     \--(not relevant & not retried)--> rephrase -> retrieve ...
                     \--(not relevant & already retried)--> fallback -> END

Retrieval uses embedding similarity over approved FAQ content, with a lexical
backup. The relevance grade is bounded to exactly one retry before the
configured support-contact fallback, per the contract.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional, TypedDict

import numpy as np
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.ai.embeddings import get_embeddings
from app.ai.llm import get_llm
from app.core.config import settings
from app.models.models import Faq
from app.repositories import repositories as repo

logger = logging.getLogger("app.ai.faq_graph")

_RELEVANCE_THRESHOLD = 0.35
_WORD_RE = re.compile(r"[a-z0-9]+")


class FaqState(TypedDict, total=False):
    question: str
    current_query: str
    retried: bool
    best_faq_id: Optional[str]
    best_answer: Optional[str]
    best_question: Optional[str]
    best_score: float
    status: str  # answered | fallback | error
    answer: str
    support_contact: Optional[str]
    sources: list[str]


def _lexical_score(a: str, b: str) -> float:
    sa = set(_WORD_RE.findall(a.lower()))
    sb = set(_WORD_RE.findall(b.lower()))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _ensure_faq_embedding(db: Session, faq: Faq) -> Optional[list[float]]:
    if faq.embedding:
        try:
            return json.loads(faq.embedding)
        except Exception:
            return None
    try:
        emb = get_embeddings()
        vec = emb.embed(f"{faq.question}\n{faq.answer}")
        faq.embedding = json.dumps(vec)
        faq.embedding_model = emb.model
        db.add(faq)
        db.commit()
        return vec
    except Exception:
        logger.warning("Could not build FAQ embedding for %s", faq.id)
        return None


def _retrieve(db: Session, query: str) -> tuple[Optional[Faq], float]:
    faqs = repo.list_faqs(db)
    if not faqs:
        return None, 0.0
    best_faq = None
    best_score = -1.0
    try:
        qvec = np.asarray(
    get_embeddings().embed(
        query,
        task_type="QUESTION_ANSWERING",
    ),
    dtype=np.float32,
)
        qn = np.linalg.norm(qvec)
    except Exception:
        qvec, qn = None, 0.0

    for faq in faqs:
        score = 0.0
        if qvec is not None and qn > 0:
            vec = _ensure_faq_embedding(db, faq)
            if vec is not None:
                v = np.asarray(vec, dtype=np.float32)
                vn = np.linalg.norm(v)
                if vn > 0 and v.shape == qvec.shape:
                    score = float(np.dot(qvec / qn, v / vn))
        # lexical backup / blend
        lex = _lexical_score(query, faq.question + " " + faq.answer)
        score = max(score, lex)
        if score > best_score:
            best_score = score
            best_faq = faq
    return best_faq, max(best_score, 0.0)


def build_faq_graph(db: Session):
    """Compile a LangGraph for one FAQ request bound to this DB session."""

    def retrieve_node(state: FaqState) -> FaqState:
        query = state.get("current_query") or state["question"]
        faq, score = _retrieve(db, query)
        if faq is None:
            return {"best_faq_id": None, "best_score": 0.0}
        return {
            "best_faq_id": faq.id,
            "best_answer": faq.answer,
            "best_question": faq.question,
            "best_score": score,
        }

    def grade_edge(state: FaqState) -> str:
        if state.get("best_score", 0.0) >= _RELEVANCE_THRESHOLD and state.get("best_answer"):
            return "answer"
        if not state.get("retried", False):
            return "rephrase"
        return "fallback"

    def rephrase_node(state: FaqState) -> FaqState:
        original = state["question"]
        new_query = original
        llm = get_llm()
        if llm.provider == "gemini":
            try:
                new_query = llm.complete(
                    "You rephrase a user's library FAQ question to improve keyword retrieval. "
                    "Return only the rephrased question.",
                    original,
                    temperature=0.3,
                ) or original
            except Exception:
                new_query = original
        else:
            # local: strip filler words to change the retrieval signal
            new_query = re.sub(r"\b(how|do|i|can|the|a|an|to|is|what|where)\b", " ", original.lower()).strip() or original
        return {"current_query": new_query, "retried": True}

    def answer_node(state: FaqState) -> FaqState:
        return {
            "status": "answered",
            "answer": state.get("best_answer") or "",
            "support_contact": None,
            "sources": [f"faq:{state.get('best_faq_id')}"] if state.get("best_faq_id") else [],
        }

    def fallback_node(state: FaqState) -> FaqState:
        return {
            "status": "fallback",
            "answer": (
                "I couldn't find a confident answer to your question in our FAQ. "
                "Please contact our support team and they'll be glad to help."
            ),
            "support_contact": settings.support_email,
            "sources": [],
        }

    graph = StateGraph(FaqState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("rephrase", rephrase_node)
    graph.add_node("answer", answer_node)
    graph.add_node("fallback", fallback_node)

    graph.set_entry_point("retrieve")
    graph.add_conditional_edges(
        "retrieve",
        grade_edge,
        {"answer": "answer", "rephrase": "rephrase", "fallback": "fallback"},
    )
    graph.add_edge("rephrase", "retrieve")
    graph.add_edge("answer", END)
    graph.add_edge("fallback", END)
    return graph.compile()


def answer_faq(db: Session, question: str) -> FaqState:
    try:
        app = build_faq_graph(db)
        result = app.invoke({"question": question, "current_query": question, "retried": False})
        # ensure required keys
        result.setdefault("status", "fallback")
        result.setdefault("answer", "")
        result.setdefault("sources", [])
        result.setdefault("support_contact", None)
        return result  # type: ignore[return-value]
    except Exception as exc:
        logger.exception("FAQ graph failed")
        return {
            "status": "error",
            "answer": "Something went wrong while answering your question. Please try again.",
            "support_contact": settings.support_email,
            "sources": [],
        }
