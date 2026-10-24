# LangChain + LangGraph migration

This branch migrates the LLM and embedding adapter away from direct `openai.OpenAI` SDK calls and introduces graph-based entry points while preserving the existing FastAPI response schemas.

## What changed

- `app/ai/llm.py`: `ChatOpenAI` from `langchain-openai` now backs the existing `get_llm().complete(...)` and `complete_json(...)` methods. Local demo fallbacks remain.
- `app/ai/embeddings.py`: `OpenAIEmbeddings` from `langchain-openai` now backs the existing `get_embeddings().embed(...)` and `embed_batch(...)` interface. The deterministic offline fallback remains.
- `app/ai/faq_graph.py`: existing LangGraph FAQ retrieve/rephrase/retry/fallback workflow retained, now uses the LangChain model wrapper through `get_llm()`.
- `app/ai/rag_graph.py`: added a catalogue-grounded RAG graph with retrieval -> relevance gate -> grounded response / not-found branch.
- `app/ai/recommendation_graph.py`: added a LangGraph entry point which wraps the existing catalogue retrieval and LLM suggestions without changing output schema or stock source of truth.
- `app/api/ai_routes.py`: recommendations endpoint now invokes the graph wrapper; FAQ endpoint remains on the existing FAQ graph.
- `requirements.txt`: adds `langchain-openai`.
- `.env.example`: documents provider configuration.

## Install and run (PowerShell)

From the `backend` directory with your venv activated:

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env  # only if you do not already have a .env
```

Put your key in `backend/.env` as `LLM_API_KEY=...` (or set `OPENAI_API_KEY` in your environment). Then start the app using the project's usual command, for example:

```powershell
python -m uvicorn app.main:app --reload
```

Do not commit `.env` or paste the API key in source code.

## Important data compatibility note

The stored vector table serializes embeddings as JSON and its configured dimension is 1536. Keep the same embedding model and dimension for queries and indexed records. Switching from the previous local hash embeddings to OpenAI embeddings does not make already-saved hash vectors semantically compatible. If your database was seeded without an OpenAI key, reindex existing books and re-create FAQ embeddings after configuring OpenAI. For a brand-new demo database, startup seeding will generate embeddings via the configured provider.

## API compatibility

`POST /api/v1/recommendations`, `POST /api/v1/chat/faq`, and `POST /api/v1/research/search` keep their current request/response contracts. `answer_from_catalog(...)` is a new service entry point for a future chat endpoint; no frontend changes are required to land this migration.

## Validation checklist

1. Install dependencies in a clean Python environment.
2. Run `python -m pytest -q` from `backend/`.
3. Check `/api/v1/health` shows OpenAI providers when a key is configured.
4. Test recommendations, FAQ retrieval and the new `answer_from_catalog(...)` service with an indexed catalogue.
5. Confirm that a missing/invalid key falls back locally as intended.

The branch has not been run in your local environment, so execute these checks before merging.
