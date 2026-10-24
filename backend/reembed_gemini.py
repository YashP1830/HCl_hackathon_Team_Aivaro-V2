"""Regenerate every stored book and FAQ embedding using Gemini.

Run from the backend directory:
    python reembed_gemini.py
"""

from __future__ import annotations

import json
import math

from google import genai
from google.genai import types
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.ai.embeddings import build_book_text
from app.models.models import Book, BookEmbedding, Faq


if not settings.resolved_gemini_api_key:
    raise RuntimeError(
        "GEMINI_API_KEY is missing. Configure backend/.env first."
    )

client = genai.Client(
    api_key=settings.resolved_gemini_api_key
)


def embed_text(
    text: str,
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> list[float]:
    """Generate a normalized vector directly from Gemini."""

    response = client.models.embed_content(
        model=settings.embedding_model,
        contents=text or " ",
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=settings.embedding_dimension,
        ),
    )

    if not response.embeddings:
        raise RuntimeError("Gemini returned no embeddings.")

    values = response.embeddings[0].values

    if not values:
        raise RuntimeError("Gemini returned an empty vector.")

    vector = [float(value) for value in values]

    if len(vector) != settings.embedding_dimension:
        raise RuntimeError(
            f"Expected {settings.embedding_dimension} dimensions, "
            f"received {len(vector)}."
        )

    norm = math.sqrt(sum(value * value for value in vector))

    if norm == 0:
        raise RuntimeError("Gemini returned a zero vector.")

    return [value / norm for value in vector]


def main() -> None:
    db = SessionLocal()

    try:
        books = db.scalars(select(Book)).all()

        for book in books:
            text = build_book_text(
                title=book.title,
                author=book.author,
                description=book.description,
                genre=book.genre,
                publisher=book.publisher,
            )

            vector = embed_text(text)

            record = db.get(BookEmbedding, book.id)

            if record is None:
                record = BookEmbedding(
                    book_id=book.id,
                    embedding=json.dumps(vector),
                    embedded_text=text,
                    embedding_model=settings.embedding_model,
                    dimension=len(vector),
                )
                db.add(record)
            else:
                record.embedding = json.dumps(vector)
                record.embedded_text = text
                record.embedding_model = settings.embedding_model
                record.dimension = len(vector)

            book.embedding_status = "ready"

        faqs = db.scalars(select(Faq)).all()

        for faq in faqs:
            text = f"{faq.question}\n{faq.answer}"
            vector = embed_text(text)

            faq.embedding = json.dumps(vector)
            faq.embedding_model = settings.embedding_model

        # Commit only after every embedding request succeeds.
        db.commit()

        print(
            f"Successfully re-embedded {len(books)} books "
            f"and {len(faqs)} FAQs using "
            f"{settings.embedding_model} "
            f"({settings.embedding_dimension} dimensions)."
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()