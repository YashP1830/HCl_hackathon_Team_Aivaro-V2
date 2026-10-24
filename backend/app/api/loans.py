"""Loan routes (KT 4.5). A user only sees/returns their own loans unless admin."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.models import User
from app.repositories import repositories as repo
from app.schemas.schemas import LoanCreate, LoanOut
from app.core.config import settings

router = APIRouter(prefix="/loans", tags=["loans"])


def _to_out(loan, book_title: str) -> LoanOut:
    now = datetime.now(timezone.utc)
    due = loan.due_at if loan.due_at.tzinfo else loan.due_at.replace(tzinfo=timezone.utc)
    is_overdue = loan.returned_at is None and due < now
    return LoanOut(
        id=loan.id,
        book_id=loan.book_id,
        book_title=book_title,
        borrowed_at=loan.borrowed_at,
        due_at=loan.due_at,
        returned_at=loan.returned_at,
        is_overdue=is_overdue,
    )


@router.get("/me", response_model=list[LoanOut])
def my_loans(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    loans = repo.list_user_loans(db, user.id)
    out = []
    for loan in loans:
        book = repo.get_book(db, loan.book_id)
        out.append(_to_out(loan, book.title if book else "(unknown)"))
    return out


@router.post("", response_model=LoanOut, status_code=status.HTTP_201_CREATED)
def borrow(body: LoanCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    book = repo.get_book(db, body.book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    if book.stock_quantity <= 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Book is out of stock")
    loan = repo.create_loan(db, user_id=user.id, book_id=book.id, period_days=settings.loan_period_days)
    # decrement stock (source of truth is the DB)
    repo.update_book(db, book, {"stock_quantity": book.stock_quantity - 1})
    return _to_out(loan, book.title)


@router.post("/{loan_id}/return", response_model=LoanOut)
def return_loan(loan_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    loan = repo.get_loan(db, loan_id)
    if not loan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    # a user may only return their own loan; admin may act on any
    if loan.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to return this loan")
    if loan.returned_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Loan already returned")

    loan.returned_at = datetime.now(timezone.utc)
    db.add(loan)
    book = repo.get_book(db, loan.book_id)
    if book:
        repo.update_book(db, book, {"stock_quantity": book.stock_quantity + 1})
    db.commit()
    db.refresh(loan)
    return _to_out(loan, book.title if book else "(unknown)")
