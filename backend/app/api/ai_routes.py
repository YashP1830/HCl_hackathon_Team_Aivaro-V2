"""AI endpoint wrappers (KT 4.1 / 4.3 / 4.4). These call the Member C services;
the route layer stays thin."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.faq_graph import answer_faq
from app.ai.recommendations import recommend_books
from app.ai.research import search_research_papers
from app.db.session import get_db
from app.schemas.schemas import (
    FaqRequest,
    FaqResponse,
    RecommendationRequest,
    RecommendationResponse,
    ResearchRequest,
    ResearchResponse,
)

router = APIRouter(tags=["ai"])


@router.post("/recommendations", response_model=RecommendationResponse)
def recommendations(body: RecommendationRequest, db: Session = Depends(get_db)):
    return recommend_books(db, body.query, top_k=body.top_k)


@router.post("/chat/faq", response_model=FaqResponse)
def faq(body: FaqRequest, db: Session = Depends(get_db)):
    result = answer_faq(db, body.question)
    return FaqResponse(
        answer=result.get("answer", ""),
        status=result.get("status", "error"),
        support_contact=result.get("support_contact"),
        sources=result.get("sources", []),
    )


@router.post("/research/search", response_model=ResearchResponse)
def research(body: ResearchRequest):
    return search_research_papers(body.topic, max_results=body.max_results)
