# Knowledge Transfer — AI-Powered Library & Research Assistant

> **Purpose of this file:** Share this file with the other two team members and their ChatGPT sessions. It is the project handover, agreed scope, integration contract, work split, and Git workflow. Read it before writing code. The aim is to build three parallel workstreams that merge cleanly.

## 1. Project in one paragraph

We are building a library and research assistant with **React + Vite** on the frontend and **FastAPI** on the backend. **PostgreSQL + pgvector** store book metadata and embeddings. When an admin adds a book, the backend saves the book and generates/upserts an embedding from its descriptive fields so semantic search can find it. A recommendation combines (1) books found in our library through pgvector and (2) additional suggestions from an LLM. Each result must always include `book_name`, `author`, and `description`, plus a status saying whether the book is available in the library, in the library but out of stock, or not in our library. LangGraph routes FAQ requests and research-paper searches. The FAQ bot retries retrieval once before showing the configured support contact. The research node uses SerpAPI to find Google Scholar results. A scheduled task emails users who have not returned borrowed books by the due date. Admin analytics reads a purchase log, calculates exact metrics in code, then uses an LLM to explain trends and prepare chart data.

## 2. Agreed architecture — keep it simple

```mermaid
flowchart TD
    USER["User / Admin"] --> UI["React + Vite"]
    UI --> API["FastAPI"]
    API --> AUTH["Authentication + role checks"]
    AUTH --> DB[("PostgreSQL + pgvector")]
    API --> AI["LangGraph / AI services"]
    AI --> DB
    AI --> SERP["SerpAPI - Google Scholar"]
    SCHED["Daily scheduler"] --> DB
    SCHED --> EMAIL["Email provider"]
    LOG["Purchase log"] --> METRICS["Python metric calculations"]
    METRICS --> LLM["LLM analytics explanation"]
    LLM --> DASH["Admin dashboard"]
    DASH --> UI
```

### Source-of-truth rules

- PostgreSQL decides whether a book exists and its current stock/availability. **Do not infer stock from an embedding or ask the LLM to decide it.**
- pgvector finds semantically relevant catalog records. Each vector must link to a stable `book_id`.
- The LLM can suggest books that are not in our database, but such suggestions must be labelled `not_in_library` after catalog matching.
- All recommendation items have the same required fields: `book_name`, `author`, `description`. `library_status` is additional required metadata.
- A loan/return event is not the same as a purchase event. Due-date email reminders read loan records; purchase analytics reads confirmed purchases.
- Exact totals/counts are calculated using code. The LLM explains precomputed metrics; it must not invent metrics or modify transactions.
- Keep the FAQ retry loop bounded: initial retrieval, one retry, then support fallback.
- Do not claim that a Google Scholar snippet means the full paper has been read.
- Do not add Redis, Kafka, multiple microservices, a second vector database, or other infrastructure unless the team can explain the specific requirement.

## 3. Three-person division of work

**The file ownership below is intentional. Avoid editing another person's workstream.** Agree on the contracts first, then work in parallel.

### Member A — Yash / Integration lead / FastAPI and database

**Primary responsibility:** backend foundation, schema, stable API routes, auth, catalog, loan/purchase event contracts, and integration/release.

**Own these paths:**

- `backend/app/main.py`
- `backend/app/api/` — all public route files and router inclusion
- `backend/app/core/` — settings, auth dependencies, role checks
- `backend/app/db/` — database connection/session and migrations
- `backend/app/models/` — canonical ORM/data models
- `backend/app/schemas/` — shared Pydantic request/response contracts
- `backend/app/repositories/` — common database queries
- `backend/tests/integration/`
- root `README.md`, root `.gitignore`, root backend dependency manifest, and backend `.env.example`

**Tasks:**

1. Inspect the actual repository first; preserve working code and naming where possible.
2. Create/confirm the FastAPI app structure, config, PostgreSQL connection, migrations, and `/health` endpoint.
3. Implement user/auth and role checks with the minimum roles actually needed (`user`, `admin`). Never trust a role sent by the frontend.
4. Own the canonical schema and migrations. Minimum entities: users, books, book embeddings, loans, FAQs/FAQ embeddings if stored in the DB, and purchase events/log metadata as agreed.
5. Implement book create/update/list/detail APIs. `POST /admin/books` must call the embedding interface after saving descriptive content and report the embedding status. Stock-only updates must not regenerate embeddings.
6. Implement/wire the endpoint wrappers for recommendations, FAQ, research, returns/loans, and analytics by calling Member C's service interfaces. Keep route files owned by Member A; Member C should supply services, not create competing route files.
7. Review PRs, resolve integration issues, run the whole application, and merge into the integration branch.

**Do not:** implement a separate duplicate FastAPI app, change the public response schema without discussion, or let all members create migrations independently.

### Member B — Frontend / React + Vite

**Primary responsibility:** user experience and API client. No backend changes.

**Own these paths:**

- `frontend/**`
- frontend dependency manifest and `frontend/.env.example`
- frontend-specific tests and UI documentation

**Tasks:**

1. Build the app shell, routing, layout, loading/error states, and reusable API client.
2. Build book/catalog search and admin create/edit form.
3. Build recommendation results. Each card must show title, author, description and a clear status badge/text: available in library, in library but out of stock, or not in library. Do not imply an external suggestion is owned by the library.
4. Build the FAQ/chat screen, research-paper result list with source links, user loan/due-date screen, and admin analytics page.
5. Consume the endpoint contracts in Section 4. If backend endpoints are not ready, use a small mock adapter with the *same* response shape; replace the adapter with real API calls later.
6. Put the backend base URL in a frontend environment variable such as `VITE_API_BASE_URL`. Do not put database, LLM, SerpAPI, or SMTP secrets in frontend variables.
7. Add frontend validation and clear error handling for 401/403, failed requests, empty search results, and slow research results.

**Do not:** modify backend models, migrations, API route files, or backend dependency files. Ask Member A to change the contract if a legitimate UI requirement is missing.

### Member C — AI workflows + scheduled notifications + analytics logic

**Primary responsibility:** LangGraph/RAG service modules and background business workflows. Member C owns the implementation internals, not public API route files or database migrations.

**Own these paths:**

- `backend/app/ai/**` — embeddings, pgvector retrieval helpers, recommendation service, FAQ workflow, SerpAPI research node, graph state/routing
- `backend/app/notifications/**` — due-date query helper, email template, notification service, sent/failure tracking logic
- `backend/app/jobs/**` — daily reminder scheduler/entry point
- `backend/app/analytics/**` — purchase-log parser, deterministic calculations, LLM explanation, chart schema validation
- tests scoped to the above modules

**Tasks:**

1. Create a single embedding interface/config that uses the selected embedding model and the same vector dimensions for documents and queries. Coordinate the dimensions with Member A before implementing the pgvector column/migration.
2. Implement `recommend_books(query, ...)`: retrieve catalog matches from pgvector; call the configured LLM for extra suggestions; normalize/deduplicate titles/authors; check catalog existence and current availability through the repository interface; return the agreed response contract.
3. Implement a small LangGraph FAQ flow: retrieve approved FAQ content, judge whether the result is relevant, reformulate and retry once, then return a support-fallback status/contact configuration if no match is found.
4. Implement the research node using SerpAPI Google Scholar results. Normalize available title/author/year/snippet/URL/DOI fields where returned; deduplicate; never fabricate missing source metadata.
5. Implement the daily reminder service: find loans that are past due and not returned, send email through a provider adapter, and prevent accidental duplicate reminder sends. Agree with Member A on the loan model and sent-status fields; do not create a conflicting migration.
6. Implement analytics processing: parse purchase events for a time window, calculate exact metrics in Python, redact unnecessary personal data, ask the LLM for a narrative and chart proposal, and validate the chart structure before returning it.
7. Return typed service results and errors so Member A can call these services without depending on your internal graph implementation.

**Do not:** edit `backend/app/main.py`, public API route files, Pydantic API schemas, ORM models, migrations, or the backend dependency manifest without coordinating with Member A. If a column is needed, propose it to Member A first.

## 4. Contract-first API and response shapes

Treat these as the initial agreed contracts. If an implementation detail needs changing, discuss it with all three members and make one coordinated update before coding against a different shape.

### 4.1 Recommendations

`POST /api/v1/recommendations`

Request:

```json
{
  "query": "Suggest me books on Generative AI",
  "top_k": 5
}
```

Response:

```json
{
  "query": "Suggest me books on Generative AI",
  "recommendations": [
    {
      "book_name": "Example catalog book",
      "author": "Example Author",
      "description": "An introduction to generative AI concepts.",
      "library_status": "in_library_available",
      "book_id": "uuid-or-null"
    },
    {
      "book_name": "Example out-of-stock book",
      "author": "Example Author",
      "description": "Covers related techniques.",
      "library_status": "in_library_out_of_stock",
      "book_id": "uuid"
    },
    {
      "book_name": "Example LLM suggestion",
      "author": "Example Author",
      "description": "Further reading related to the query.",
      "library_status": "not_in_library",
      "book_id": null
    }
  ]
}
```

Required fields per recommendation: `book_name`, `author`, `description`, `library_status`, `book_id`. The first three fields are mandatory for every result irrespective of database presence. Use a consistent fallback such as `"Author not confirmed"` if the author cannot be verified. `book_id` is null for suggestions with no matching catalog record.

Only these initial `library_status` values are allowed:

- `in_library_available` — catalog row exists and current stock is greater than zero.
- `in_library_out_of_stock` — catalog row exists but current stock is zero/unavailable.
- `not_in_library` — there is no sufficiently confident matching catalog record; it is an LLM-only suggestion.

The LLM must not decide the status. The service checks results against PostgreSQL and obtains current stock there. Avoid false `not_in_library` labels by normalizing punctuation/case and comparing title/author carefully.

### 4.2 Book administration

- `GET /api/v1/books?q=&page=1&page_size=20` — list/search book catalog.
- `GET /api/v1/books/{book_id}` — book details and current stock.
- `POST /api/v1/admin/books` — admin creates book and triggers embedding sync.
- `PATCH /api/v1/admin/books/{book_id}` — admin edits descriptive fields or stock.

Example create request:

```json
{
  "title": "Generative AI Fundamentals",
  "author": "Example Author",
  "description": "An introduction to generative AI.",
  "genre": "Artificial Intelligence",
  "publisher": "Example Publisher",
  "publication_year": 2025,
  "stock_quantity": 4
}
```

Recommended response includes the stored `book`, its `embedding_status` (`pending`, `ready`, or `failed`), and a safe error/status detail when the embedding fails. If the row saves but vector creation fails, retain the book row and expose retry; do not report indexing as ready.

### 4.3 FAQ chatbot

`POST /api/v1/chat/faq`

Request: `{ "question": "How do I borrow a book?" }`

Response shape:

```json
{
  "answer": "Use the borrowing page to select an available book.",
  "status": "answered",
  "support_contact": null,
  "sources": []
}
```

When no reliable FAQ is found after one retry, use `status: "fallback"`, a transparent message, and a configured `support_contact`. Never hardcode imaginary support details. Suggested statuses: `answered`, `fallback`, `error`.

### 4.4 Research paper search

`POST /api/v1/research/search`

Request: `{ "topic": "retrieval augmented generation", "max_results": 5 }`

Response shape:

```json
{
  "topic": "retrieval augmented generation",
  "results": [
    {
      "title": "Paper title from search result",
      "authors": ["Author where available"],
      "year": 2025,
      "snippet": "Search-result snippet where available",
      "url": "https://example.org/paper",
      "doi": null
    }
  ]
}
```

Use values from SerpAPI results only; fields not returned by the provider can be null or omitted per the agreed schema. Label search snippets as snippets, not full-paper summaries.

### 4.5 Loans, notifications, analytics

- `GET /api/v1/loans/me` — authenticated user sees their own loan records.
- `POST /api/v1/loans/{loan_id}/return` — authenticated user can return only a loan permitted by policy; admin can act according to policy.
- The daily scheduler is an internal job, not a browser endpoint.
- `GET /api/v1/admin/analytics?from=YYYY-MM-DD&to=YYYY-MM-DD` — admin-only; returns metrics plus LLM narrative and validated chart data.
- Only confirmed purchase events should be included in purchase analytics. Loans are a separate event type.

Suggested error response (consistent across endpoints):

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request is invalid."
  },
  "request_id": "request-id"
}
```

Use normal HTTP statuses: 401 unauthenticated, 403 forbidden, 404 missing/inaccessible record, 409 conflict, 422 validation failure, 429 rate limited, and 5xx unexpected failure.

## 5. Shared data schema — initial minimum

Member A owns the actual ORM models and migrations; Member C requests additions through A rather than editing migrations.

### `users`

- `id` UUID primary key
- `name`, `email` (unique), `password_hash` or external auth subject
- `role` (`user` or `admin` at first), `created_at`

### `books`

- `id` UUID primary key
- `title`, `author`, `description`, `genre`, `publisher`, `publication_year`
- `stock_quantity` integer (non-negative), `availability_status` as appropriate
- `embedding_status` (`pending`, `ready`, `failed`), timestamps

### `book_embeddings`

- `book_id` foreign key/primary key referencing `books.id`
- `embedding` pgvector column with dimension equal to the configured embedding model output
- `embedded_text`, `embedding_model`, `updated_at`

### `loans`

- `id`, `user_id`, `book_id`, `borrowed_at`, `due_at`, `returned_at`
- `reminder_sent_at` or a notification record with a unique key for that loan/due-date reminder

### `faqs` and FAQ embeddings

- `id`, `question`, `answer`, `category`, `updated_at`
- FAQ vector records link to an FAQ ID. The exact physical schema is finalized by Member A with input from Member C.

### Purchase events

Keep a structured purchase log with at least `purchase_id`, `user_id`, `book_id`, `book_title`, `purchased_at`, `quantity`, and `amount` if revenue is relevant. A CSV file is acceptable for a small prototype, but concurrent writes are risky. Prefer an append-only PostgreSQL purchase-events table as the source of truth and export a CSV if a file is explicitly needed. Do not log sensitive data unnecessarily.

### pgvector synchronization rule

The embedded text contains stable descriptive fields such as title, author, description, genre, and publisher. It must not contain mutable stock count. If descriptive text changes, regenerate the vector. If only stock changes, update PostgreSQL only. The save/index flow should not tell the admin indexing succeeded until the vector upsert succeeds. If embedding fails, preserve the catalog record, mark indexing failed, and allow a retry.

## 6. Agreed LangGraph responsibilities

Keep the graph small. A request should go to the right service; do not build an autonomous multi-agent framework when a simple node/conditional edge is enough.

```mermaid
flowchart TD
    Q["Incoming request"] --> ROUTER{"Request type?"}
    ROUTER --> REC["Recommendation service"]
    ROUTER --> FAQ["FAQ retrieval"]
    ROUTER --> RES["Google Scholar research node"]
    FAQ --> GRADE{"Relevant FAQ?"}
    GRADE -->|"Yes"| ANSWER["Return FAQ answer"]
    GRADE -->|"No"| RETRY["Rephrase and retry once"]
    RETRY --> GRADE2{"Relevant now?"}
    GRADE2 -->|"Yes"| ANSWER
    GRADE2 -->|"No"| SUPPORT["Support contact fallback"]
    REC --> RESULTS["Structured recommendations"]
    RES --> PAPERS["Paper metadata and links"]
```

### Recommendation service pseudoflow

1. Validate the query.
2. Embed the query and search pgvector for catalog candidates.
3. Fetch book rows and current stock from PostgreSQL.
4. Ask the LLM for additional candidate books using a strict structured output schema with only `book_name`, `author`, and `description` as book content.
5. Normalize/compare the LLM candidates against catalog titles/authors and deduplicate against vector results.
6. Set `library_status` and `book_id` from the actual database match—not from the LLM.
7. Return a common response shape for all books.

### FAQ pseudoflow

`retrieve → relevance check → (answer OR rephrase once → retrieve/check → answer OR support fallback)`.

### Research pseudoflow

`validate topic → SerpAPI Google Scholar search → normalize/deduplicate → return metadata and links`.

Use timeouts, result limits, and safe error handling. External pages and snippets are untrusted inputs; they cannot override the system's permissions or tool rules.

## 7. Recommended repository structure

Adapt this to the current repo rather than forcing a destructive restructure:

```text
project-root/
├── README.md
├── KNOWLEDGE_TRANSFER.md
├── .gitignore
├── backend/
│   ├── .env.example
│   ├── requirements.txt          # or pyproject.toml, selected once by Member A
│   ├── app/
│   │   ├── main.py
│   │   ├── api/                  # Member A: public endpoint wrappers
│   │   ├── core/                 # Member A: config/auth/permissions
│   │   ├── db/                   # Member A: session/migrations
│   │   ├── models/               # Member A: ORM models
│   │   ├── schemas/              # Member A: stable Pydantic contracts
│   │   ├── repositories/         # Member A: shared database access
│   │   ├── ai/                   # Member C: embeddings, pgvector retrieval, LangGraph
│   │   ├── notifications/        # Member C: reminder/email service
│   │   ├── jobs/                 # Member C: scheduled job entry point
│   │   └── analytics/            # Member C: log parser, calculations, LLM report
│   └── tests/
└── frontend/
    ├── .env.example
    ├── package.json
    └── src/                      # Member B: frontend only
```

If the project already has a working structure, keep it and document the mapping instead of moving everything just to match this example.

## 8. How to work in parallel without breaking merges

### Before coding (required)

1. All three members read this file and the README.
2. Member A pushes the initial repository skeleton, canonical schema/models, Pydantic contracts, and example environment files to the integration branch.
3. All members review Section 4 and confirm response field names/status values. Freeze the contract for the first milestone.
4. Each member creates a separate feature branch from the agreed integration branch.
5. Do not start three independent implementations of the same API or schema.

### Branch names

- `feature/backend-contracts` — Member A
- `feature/frontend-ui` — Member B
- `feature/ai-workflows` — Member C

Use pull requests into `develop` (integration branch). Merge `develop` into `main` only after the integration checklist passes. If the repo currently uses `main` only, create/agree on `develop` before feature work, or use PRs into `main` with the same review gates.

### File ownership / merge rules

- Member A is the **only person** who edits ORM models, database migrations, Pydantic API schemas, central router wiring, backend dependency manifest, and public API route files.
- Member B edits **only `frontend/**`**.
- Member C edits **only AI, notifications, jobs, and analytics service modules** listed above. For a schema change, post the proposed field and reason; Member A implements it.
- Never have two people independently rename route names or response keys. Keep the schema in one place and include an example response in PRs.
- Do not commit `.env`, API keys, SMTP credentials, or database passwords.
- Keep PRs small and single-purpose. Never force-push to a shared branch.

### Daily sync format

At the start/end of each work session, each member posts:

1. **Done:** what merged or is complete.
2. **Next:** the next small deliverable.
3. **Contract/schema changes requested:** exact field/path and why.
4. **Blockers:** errors or interface questions.
5. **Files changed:** so the team can spot ownership overlap early.

### Merge order

1. Member A merges shared scaffold, database schema, API schemas, and empty endpoint stubs.
2. Member C merges AI/service modules that implement the agreed interfaces.
3. Member B merges frontend calling those stable endpoints (can use contract-shaped mocks while waiting).
4. Member A integrates router calls, resolves configuration, and runs the full test set.
5. Team tests the whole user journey before promoting to `main`.

## 9. Tests required before merge

### Backend/contract

- API starts and `/health` works with test configuration.
- Schema/migrations can build a clean local test database.
- Unauthorized requests are rejected; a user cannot inspect another user's loan.
- Request and response JSON match Section 4.

### Recommendations

- An in-stock catalog match returns `in_library_available`.
- A matching book with zero stock returns `in_library_out_of_stock`.
- An LLM suggestion with no catalog match returns `not_in_library` and `book_id: null`.
- Every result has all three required string fields: `book_name`, `author`, `description`.
- A stock-only update does not call the embedding model.
- If embedding generation fails, the book remains saved but is not marked indexed/ready.
- LLM suggestion matching is deduplicated against catalog results.

### FAQ/research

- FAQ match returns the approved answer.
- No match triggers no more than one retry and then the configured support fallback.
- Empty/failing SerpAPI results return a safe no-results/error response, not fabricated citations.

### Reminder/analytics

- Returned loans do not receive reminders.
- Overdue unreturned loans are selected; duplicate reminder delivery is prevented according to the reminder policy.
- Analytics totals are calculated in code and can be checked against fixture data.
- LLM chart output is schema-validated before rendering.

### Frontend

- Empty/loading/error/success states work.
- Status labels are distinct and accessible.
- API base URL comes from frontend environment config.
- UI does not assume the LLM suggestion belongs to the library.

## 10. Definition of done for the first end-to-end milestone

The first milestone is complete when:

- [ ] An admin can add a book and see its embedding status.
- [ ] A book's descriptive fields are embedded in pgvector and linked to its `book_id`.
- [ ] Querying a topic returns library matches and additional LLM suggestions in a common structured response.
- [ ] The UI shows available, out-of-stock, and not-in-library distinctions correctly.
- [ ] FAQ chatbot answers from stored FAQ content or shows the configured support contact after one retry.
- [ ] Research search returns Google Scholar results via SerpAPI with available source links.
- [ ] A due-date task can identify unreturned overdue loans and send a test email safely.
- [ ] Analytics reads a fixture purchase log, computes metrics, and renders a validated report/chart response.
- [ ] All environment secrets are external to Git and all three members can run the project using the setup instructions.
- [ ] A clean clone can start the app and the agreed smoke tests pass.

## 11. Environment configuration

Keep actual secret values local and out of Git. Member A owns backend configuration shape; each member creates their own local `.env` from `.env.example`.

Example backend keys (the actual code may rename them, but agree once):

```dotenv
APP_ENV=development
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/library_assistant
API_PREFIX=/api/v1
LLM_API_KEY=
LLM_MODEL=
EMBEDDING_MODEL=
EMBEDDING_DIMENSION=
SERPAPI_API_KEY=
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
EMAIL_FROM=
SUPPORT_EMAIL=
FRONTEND_ORIGIN=http://localhost:5173
```

Frontend example:

```dotenv
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

`VITE_` variables are exposed to the browser; never put a private key or secret in one.

## 12. Suggested build order

**Phase 1 — Agree and scaffold (Member A leads):** repo structure, environment config, database models/migration, API schemas, endpoint stubs, and `/health`.

**Phase 2 — Parallel independent work:**
- Member A: auth, book CRUD, loans, repository/query functions and API wrappers.
- Member B: UI shell, API client, forms/cards/status views using frozen contracts and mocks.
- Member C: embedding/retrieval implementation, recommendation/FAQ/research services, notification and analytics services using agreed repository interfaces.

**Phase 3 — Integration:** Member A wires service interfaces into API route wrappers; team resolves mismatches in a short coordination call or PR comments. Do not silently fork the contract.

**Phase 4 — End-to-end test:** test from admin book creation to visible recommendation, then FAQ fallback, research search, loan reminder, and analytics report.

**Phase 5 — Polish and demo:** seeded demo data, clear UI states, logs without secrets, setup instructions, and a short interview walkthrough.

## 13. Prompt to give Member B's ChatGPT (Frontend)

Copy the prompt below into the teammate's ChatGPT along with this `KNOWLEDGE_TRANSFER.md`:

> You are the frontend engineer for the AI-Powered Library & Research Assistant. Read the entire attached `KNOWLEDGE_TRANSFER.md` and follow it as the agreed contract. Your ownership is `frontend/**` only. Implement the React + Vite frontend: app shell, catalog search/admin book form, semantic recommendations, FAQ chat, research results, user loan/due-date view, and admin analytics dashboard. Use the exact request/response shapes and statuses in Section 4. Each recommendation must show `book_name`, `author`, `description`, and the status `in_library_available`, `in_library_out_of_stock`, or `not_in_library`. Use `VITE_API_BASE_URL` and a typed API client; use mock data with the exact real contract if endpoints are not ready. Do not edit backend files, DB schemas, migrations, secrets, or public API contracts. Before coding, inspect the actual repository and report the current structure; then propose a small plan, implement only your assigned files, add frontend tests where practical, and provide changed-file list plus run/test commands. Ask the team before proposing any contract change.

## 14. Prompt to give Member C's ChatGPT (AI + jobs)

Copy the prompt below into the teammate's ChatGPT along with this `KNOWLEDGE_TRANSFER.md`:

> You are the AI/backend-services engineer for the AI-Powered Library & Research Assistant. Read the entire attached `KNOWLEDGE_TRANSFER.md` and follow it as the agreed contract. Your ownership is `backend/app/ai/**`, `backend/app/notifications/**`, `backend/app/jobs/**`, and `backend/app/analytics/**` plus their tests. Do not edit public API route files, ORM models, migrations, Pydantic API schemas, `main.py`, or the backend dependency manifest; Member A owns those. Before implementing, inspect the actual repository and confirm the database/vector and service interfaces available. Implement: (1) book embedding + pgvector retrieval; (2) recommendation merge of pgvector results and LLM-only candidates with strict `book_name`, `author`, `description` fields and DB-derived statuses; (3) FAQ retrieve → relevance check → one retry → support fallback; (4) SerpAPI Google Scholar research results; (5) overdue unreturned-loan email reminder service with duplicate prevention; (6) deterministic purchase-log analytics plus LLM narrative/chart validation. Ask Member A for schema/interface changes instead of changing models yourself. Use typed inputs/outputs, bounded calls, safe errors, and tests. Provide exact service signatures for Member A to wire into route wrappers, a list of changed files, required dependencies/env variables, and run/test commands. Do not claim functionality is integrated until the full app has been tested.

## 15. Shared prompt for any new ChatGPT session

> This project is a three-person team effort. Read `KNOWLEDGE_TRANSFER.md` first and treat its architecture, file ownership, API contracts, response statuses, and merge rules as the source of truth. First inspect the actual repository and report which parts already exist; do not overwrite existing working code. Only work on the assigned role/files. Avoid broad refactors, avoid adding new services/dependencies without a reason, and do not silently change API schemas. If a dependency or data field is missing, explain the smallest proposed contract change for the team before editing. At the end, summarize files changed, tests run/results, environment variables required, known gaps, and exact merge/run instructions.

## 16. Project-specific decisions to confirm together

Before implementation, make these explicit in the team chat and then record them in `.env.example` or the README:

1. Which LLM provider/model and embedding model are used; what is the embedding dimension?
2. Does “purchase” mean a real purchase, or is the log really a loan/checkout event? Keep names and metrics accurate.
3. What exact policy should reminders follow: once on the due date, once daily while overdue, or another cadence?
4. What is the actual customer-support email/contact?
5. Which email provider is used locally and in deployment?
6. How is admin identity provisioned? Do not let users set their own role during registration.
7. Does the current repository already have models/routes, and what naming conventions should be preserved?

**Team rule:** when a detail is not yet known, use a configuration variable or mark it as a decision to confirm. Do not invent production credentials, provider behavior, measured latency, or features that have not been implemented.
