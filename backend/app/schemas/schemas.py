"""Shared Pydantic request/response contracts (KT Section 4)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field

LibraryStatus = Literal["in_library_available", "in_library_out_of_stock", "not_in_library"]
FaqStatus = Literal["answered", "fallback", "error"]


# ---------------- Auth ----------------
class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=6, max_length=256)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str
    email: EmailStr


class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str

    model_config = {"from_attributes": True}


# ---------------- Books ----------------
class BookBase(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    author: str = Field(min_length=1, max_length=512)
    description: str = ""
    genre: str = ""
    publisher: str = ""
    publication_year: Optional[int] = None
    stock_quantity: int = Field(default=0, ge=0)


class BookCreate(BookBase):
    pass


class BookUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=512)
    author: Optional[str] = Field(default=None, max_length=512)
    description: Optional[str] = None
    genre: Optional[str] = None
    publisher: Optional[str] = None
    publication_year: Optional[int] = None
    stock_quantity: Optional[int] = Field(default=None, ge=0)


class BookOut(BaseModel):
    id: str
    title: str
    author: str
    description: str
    genre: str
    publisher: str
    publication_year: Optional[int]
    stock_quantity: int
    availability_status: str
    embedding_status: str

    model_config = {"from_attributes": True}


class BookListResponse(BaseModel):
    items: list[BookOut]
    total: int
    page: int
    page_size: int


class AdminBookResponse(BaseModel):
    book: BookOut
    embedding_status: str  # pending | ready | failed
    embedding_detail: Optional[str] = None


# ---------------- Recommendations ----------------
class RecommendationRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=25)


class RecommendationItem(BaseModel):
    book_name: str
    author: str
    description: str
    library_status: LibraryStatus
    book_id: Optional[str] = None


class RecommendationResponse(BaseModel):
    query: str
    recommendations: list[RecommendationItem]


# ---------------- FAQ ----------------
class FaqRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class FaqResponse(BaseModel):
    answer: str
    status: FaqStatus
    support_contact: Optional[str] = None
    sources: list[str] = []


# ---------------- Research ----------------
class ResearchRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=20)


class ResearchResult(BaseModel):
    title: str
    authors: list[str] = []
    year: Optional[int] = None
    snippet: Optional[str] = None
    url: Optional[str] = None
    doi: Optional[str] = None


class ResearchResponse(BaseModel):
    topic: str
    results: list[ResearchResult]
    note: Optional[str] = None  # transparency, e.g. "live search unavailable"


# ---------------- Loans ----------------
class LoanOut(BaseModel):
    id: str
    book_id: str
    book_title: str
    borrowed_at: datetime
    due_at: datetime
    returned_at: Optional[datetime]
    is_overdue: bool

    model_config = {"from_attributes": True}


class LoanCreate(BaseModel):
    book_id: str


# ---------------- Analytics ----------------
class AnalyticsMetric(BaseModel):
    label: str
    value: float


class ChartSeries(BaseModel):
    label: str
    data: list[float]


class ChartData(BaseModel):
    type: Literal["bar", "line", "pie"]
    title: str
    categories: list[str]
    series: list[ChartSeries]


class AnalyticsResponse(BaseModel):
    from_date: str
    to_date: str
    totals: dict[str, float]
    top_books: list[dict]
    narrative: str
    charts: list[ChartData]
    llm_used: bool


# ---------------- Errors ----------------
class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
    request_id: Optional[str] = None
