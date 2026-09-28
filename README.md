# Requirements Studio

Requirements gathering application with document ingestion, vector search, grounded RAG question answering, and a LangGraph SDLC recommendation workflow. RAG and SDLC recommendation services combine project metadata, questionnaire answers, and retrieved document chunks. The SDLC workflow scores seven supported lifecycle models and persists recommendation history. It does not implement a multi-agent system or automatic final reports.

## RAG architecture

```mermaid
flowchart TD
  Q[Project question] --> RET[Project-scoped retriever]
  RET --> CH[Top-k chunks above score threshold]
  PR[Project metadata] --> PB[Prompt builder]
  QR[Questionnaire answers] --> PB
  CH --> PB
  Q --> PB
  PB --> LLM[Configured LangChain chat model]
  LLM --> A[Grounded answer with inline chunk citations]
  A --> DB[(PostgreSQL conversation and messages)]
  Q --> DB
```

## Project structure

```text
backend/
  alembic/versions/             # initial schema through 0004_rag_conversations
  app/
    api/routes/                 # projects, documents, search, RAG, SDLC recommendations, health
    core/                       # settings, DB session, error handling
    models/                     # project, questionnaire, documents, recommendations, conversations, messages
    parsers/                    # PDF, DOCX, TXT parsers
    repositories/               # database queries
    schemas/                    # API request/response models
    services/                   # ingestion, vector, prompt, LLM, RAG, scoring, and LangGraph services
  data/uploads/                 # uploaded source documents
  data/chroma/                  # persistent ChromaDB collection
  tests/                        # API, RAG, vector, parser tests
  requirements.txt
  alembic.ini
frontend/                       # React + Vite dashboard and project workflows
  src/components/               # shared navigation, states, error boundary, toasts
  src/lib/                       # TanStack Query client, cache keys, validation
  src/pages/                     # home, project dashboard, questionnaire, docs, chat, recommendation
  src/services/api.ts            # typed FastAPI client
  src/test/                      # Vitest and React Testing Library setup
docker-compose.yml
.env.example
```

## Phase 8 frontend dashboard

The frontend uses FastAPI as its source of truth. TanStack Query caches reads, retries transient backend failures, and invalidates project/document/recommendation/conversation queries after mutations. API failures surface in-page and through toast notifications, with an application-wide error boundary for unexpected render errors. No browser storage is required for project persistence.

```mermaid
flowchart LR
  UI[React routes] --> Q[TanStack Query cache]
  Q --> API[Typed API service]
  API --> FASTAPI[FastAPI REST API]
  FASTAPI --> PG[(PostgreSQL)]
  FASTAPI --> CHROMA[(ChromaDB)]
  FASTAPI --> LLM[Gemini or OpenAI]
```

Routes:

| Route | Screen |
|---|---|
| `/` | Analytics overview and backend project list |
| `/projects/new` | New project questionnaire flow |
| `/projects/:projectId/questionnaire` | Existing project questionnaire |
| `/projects/:projectId` | Project dashboard, questionnaire summary, documents, embedding status, recommendation, recent conversations |
| `/projects/:projectId/recommendation` | Generate/view recommendation, confidence, reasoning, risks, mitigations, testing and delivery notes, history |
| `/projects/:projectId/chat` | RAG chat, conversation history, source citations |
| `/projects/:projectId/documents` | Upload, view metadata/chunk counts, embed, and delete documents |

Frontend configuration is in `frontend/.env` (copy from `frontend/.env.example`). `VITE_API_BASE_URL` defaults to `http://127.0.0.1:8000`. LLM and embedding provider keys are configured on the backend in the root `.env`; see `.env.example`.

Install and run the frontend from the repository root:

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Build and run the frontend tests:

```powershell
npm run build
npm run test
```

Backend integration used by dashboard pages:

| Feature | Endpoint |
|---|---|
| Project list/details/update | `GET /api/projects`, `GET /api/projects/{id}`, `PUT /api/projects/{id}` |
| Documents, deletion, embedding | `GET/POST /api/projects/{id}/documents`, `DELETE /api/projects/{id}/documents/{doc_id}`, `POST /api/projects/{id}/documents/{doc_id}/embed`, `GET /api/projects/{id}/documents/{doc_id}/embedding-status` |
| Search and RAG chat | `POST /api/search`, `POST /api/projects/{id}/ask`, `GET /api/projects/{id}/conversations`, `GET /api/projects/{id}/conversations/{conversation_id}` |
| SDLC recommendations | `POST /api/projects/{id}/recommend-sdlc`, `GET /api/projects/{id}/recommendation-history` |
| Cross-project analytics | `GET /api/analytics/summary` |

The backend also exposes document preview/chunk APIs, RAG evaluation/debug endpoints, and SDLC comparison. See Swagger UI at `http://127.0.0.1:8000/docs` for full request and response schemas.

## Setup and run

Requires Python 3.11+, Docker Desktop, and Node.js for the frontend. Local sentence-transformer embeddings are used by default, and Gemini generates RAG answers by default. Set `GEMINI_API_KEY` in `.env` before using `/ask` or `/evaluate-rag`. From the repository root:

```powershell
Copy-Item .env.example .env
# Set GEMINI_API_KEY in .env before using /ask or /evaluate-rag.
docker compose up -d postgres
Set-Location backend
py -m venv ..\.venv
..\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

PostgreSQL uses host port `5433` to avoid conflicts with a local PostgreSQL service. Embeddings default to `EMBEDDING_PROVIDER=local` and `EMBEDDING_MODEL=all-MiniLM-L6-v2`; the first local embedding run downloads the model weights. To use OpenAI embeddings, set `EMBEDDING_PROVIDER=openai` and `EMBEDDING_MODEL=text-embedding-3-small` in `.env` and provide `OPENAI_API_KEY`. RAG chat defaults to `LLM_PROVIDER=gemini`, `GEMINI_MODEL=gemini-3.8-flash`, and `GEMINI_FALLBACK_MODEL=gemini-3.6-flash,gemini-3.7-flash`; set `GEMINI_API_KEY` in `.env`. Temporary Gemini capacity errors (429/5xx) try each configured fallback model in order. For backward compatibility, set `LLM_PROVIDER=openai`, `LLM_MODEL=gpt-4o-mini`, and `OPENAI_API_KEY` to use OpenAI chat instead. Chat provider/model settings are independent of the embedding provider. `CHROMA_PERSIST_DIRECTORY` and `CHROMA_COLLECTION_NAME` continue to configure the same persistent vector storage. Gemini uses Google's `google-genai` SDK; OpenAI chat remains on `langchain-openai`.

Changing an existing Chroma collection from OpenAI vectors to MiniLM vectors requires a one-time reindex because their vector dimensions differ. Back up or remove `backend/data/chroma`, then regenerate embeddings for the uploaded documents. PostgreSQL document chunks remain available for re-embedding.

Run the frontend separately with `cd frontend`, `npm install`, and `npm run dev`.

## Frontend project submission

The questionnaire frontend calls FastAPI directly at `http://127.0.0.1:8000` by default. To use another backend URL, set `VITE_API_BASE_URL` in `frontend/.env`. Project lists, project details, questionnaire answers, and uploaded documents are loaded from the backend; the frontend does not use browser storage for project persistence. A new questionnaire draft is held only while its tab remains open until submission.

The submit flow uses these APIs:

| Method | Endpoint | Submission step |
|---|---|---|
| POST | `/api/projects` | Create a project and receive its backend project ID |
| PUT | `/api/projects/{id}` | Update project profile fields when continuing an existing project |
| POST | `/api/projects/{id}/questionnaire` | Save questionnaire responses |
| POST | `/api/projects/{id}/documents` | Upload each selected PDF, DOCX, or TXT file (`file` multipart field) |
| GET | `/api/projects/{id}` | Load project, questionnaire, and documents on open/refresh |
| GET | `/api/projects?limit=100&offset=0` | Load existing projects from the backend |

To manually verify the frontend and PostgreSQL persistence:

1. Start PostgreSQL, apply migrations, and run FastAPI using the commands in Setup and run.
2. In another terminal run `cd frontend`, `npm install` (first run only), and `npm run dev`.
3. Open the Vite URL, choose **New project**, complete the questionnaire, optionally attach documents, and submit.
4. Confirm the success page displays the backend project ID. Refresh that page; project details and saved answers should load again from FastAPI. Use **Home** → **Existing project** to verify the project appears from the database.
5. Confirm PostgreSQL rows (replace the query as needed):

```powershell
docker exec requirements-postgres psql -U requirements -d requirements_db -c "SELECT id, project_name FROM projects ORDER BY created_at DESC LIMIT 5;"
docker exec requirements-postgres psql -U requirements -d requirements_db -c "SELECT project_id, requirement_stability, risk_level FROM questionnaire_responses ORDER BY created_at DESC LIMIT 5;"
docker exec requirements-postgres psql -U requirements -d requirements_db -c "SELECT project_id, original_filename FROM uploaded_documents ORDER BY created_at DESC LIMIT 5;"
```

The database check for `uploaded_documents` is applicable only when a file was attached. The upload endpoint also stores the original file and parsed chunks under the backend data directory.

## Database and migrations

`conversations` stores a project ID and creation time. `messages` stores its conversation ID, role (`user` or `assistant`), content, and creation time. Foreign keys cascade on project/conversation deletion. Conversation messages are returned in insertion order.

Apply and inspect migrations from `backend/`:

```powershell
alembic upgrade head
alembic current
```

Phase 6 adds `0004_rag_conversations` after the vector metadata migration. Roll back only the conversation schema with `alembic downgrade 0003_vector_search_metadata`. ChromaDB persists separately in `backend/data/chroma`; uploaded originals are in `backend/data/uploads`.

## APIs

Swagger UI: `http://127.0.0.1:8000/docs`; OpenAPI JSON: `/openapi.json`.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/projects/{id}/documents` | Upload and chunk a PDF, DOCX, or TXT |
| POST | `/api/projects/{id}/documents/{doc_id}/embed` | Create and persist chunk vectors |
| POST | `/api/search` | Vector search scoped to a project |
| POST | `/api/projects/{id}/ask` | Ask a grounded project question |
| POST | `/api/projects/{id}/evaluate-rag` | Inspect retrieved chunks, selected context, final prompt, answer, and metrics |
| GET | `/api/projects/{id}/retrieval-debug` | Inspect ranked retrieval results and metadata without an LLM call |
| GET | `/api/projects/{id}/conversations/{conversation_id}` | Read persisted conversation history |
| POST | `/api/projects/{id}/recommend-sdlc` | Run LangGraph retrieval, questionnaire scoring, Gemini/OpenAI reasoning, and persist the recommendation |
| GET | `/api/projects/{id}/recommendation-history` | List persisted LangGraph recommendation runs |
| POST | `/api/projects/{id}/compare-sdlc` | Compare two supported SDLC models using questionnaire and retrieved evidence |

Create a project and upload a document using the existing project endpoints. Embed it before asking document-grounded questions:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/projects/$projectId/documents" -F "file=@backend/sample_data/meeting_notes.txt;type=text/plain"
curl.exe -X POST "http://127.0.0.1:8000/api/projects/$projectId/documents/$documentId/embed"
curl.exe -X POST "http://127.0.0.1:8000/api/projects/$projectId/ask" -H "Content-Type: application/json" -d "{\"question\":\"Which SDLC model fits the project evidence?\",\"top_k\":5,\"score_threshold\":0.2}"
curl.exe -X POST "http://127.0.0.1:8000/api/projects/$projectId/evaluate-rag" -H "Content-Type: application/json" -d "{\"question\":\"Which SDLC model fits the project evidence?\",\"top_k\":5,\"score_threshold\":0.2}"
curl.exe "http://127.0.0.1:8000/api/projects/$projectId/retrieval-debug?question=loan%20decision&top_k=5&score_threshold=0.2"
```

For a direct PowerShell test of both RAG chat endpoints, configure `GEMINI_API_KEY` in `.env`, restart FastAPI, then run:

```powershell
$projectId = "8f6a425d-1824-46a3-a874-ffa36c0c5804"
$requestBody = @{ question = "What risks and requirements are described in the uploaded document?"; top_k = 5; score_threshold = 0.2 } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/projects/$projectId/ask" -Method Post -ContentType "application/json" -Body $requestBody
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/projects/$projectId/evaluate-rag" -Method Post -ContentType "application/json" -Body $requestBody
```

Use an existing project ID that has been created in this backend if the example ID is not present in your database. The `ask` result contains the answer, citations, and conversation ID; `evaluate-rag` also shows the selected context, rendered prompts, and request metrics.

Ask request fields: `question` (required), `top_k` (default 5, max 50), `score_threshold` (default 0.2, range -1 through 1), `filters` (optional Chroma metadata filters), and `conversation_id` (optional to continue a conversation). The response contains `answer`, source `chunk_id`/`document_id`/`score` objects, and a `conversation_id` to continue or fetch the conversation.

Each answer is prompted to use only supplied project/questionnaire/retrieved context, cite used chunks inline as `[chunk_id=<id>]`, and explicitly say when information is insufficient. The source list contains retrieved chunks that met the score threshold. Answers are generated only at request time; this phase does not generate reports or recommendations automatically.

`evaluate-rag` returns one-based chunk ranks, scores, text and metadata, the selected context, both rendered prompts, the generated answer, and metric values. `retrieval-debug` accepts optional JSON metadata filters through the `filters` query parameter, for example `filters=%7B%22filename%22%3A%22meeting_notes.txt%22%7D`. RAG logs include retrieval time, prompt character size, prompt token estimate, answer-generation time, and answer token estimate; prompt and answer contents are not logged. Token values are estimates based on word and punctuation units.

### LangGraph SDLC recommendations

The recommendation workflow is:

```mermaid
flowchart LR
  START --> Q[Collect questionnaire and project context]
  Q --> RET[Retrieve relevant ChromaDB chunks]
  RET --> ANALYZE[Analyze project characteristics]
  ANALYZE --> SCORE[Score seven supported SDLC models]
  SCORE --> LLM[Generate grounded rationale with configured Gemini or OpenAI provider]
  LLM --> SAVE[Persist recommendation run in PostgreSQL]
  SAVE --> END
```

The deterministic scoring engine returns a 0–100 score for Waterfall, V-Model, Incremental, Iterative, Spiral, Agile Scrum, and RAD. Scores come from questionnaire answers plus small adjustments for retrieved document evidence; unembedded documents do not affect a recommendation. The LLM explains the top-ranked supported model and cites retrieved document claims with `[chunk_id=<id>]`. DevOps is treated as a delivery/operations practice and Kanban as a flow-management method; neither appears in the SDLC scorecard, alternatives, or comparison choices. The recommendation response includes the model scores, confidence estimate, alternatives, strengths, risks, implementation notes, and source chunks. The scoring revision is versioned as `langgraph_v2`; older recommendation history is retained in PostgreSQL but excluded from current recommendation views. If the questionnaire has not been saved, recommendation generation returns HTTP 409.

Example PowerShell requests (set `$projectId` to a project with a saved questionnaire):

```powershell
$projectId = "8f6a425d-1824-46a3-a874-ffa36c0c5804"
$recommendBody = @{ top_k = 5 } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/projects/$projectId/recommend-sdlc" -Method Post -ContentType "application/json" -Body $recommendBody
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/projects/$projectId/recommendation-history?limit=20&offset=0"
$compareBody = @{ model_a = "Agile Scrum"; model_b = "V-Model"; top_k = 5 } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/projects/$projectId/compare-sdlc" -Method Post -ContentType "application/json" -Body $compareBody
```

`compare-sdlc` returns each model's fit rationale and score, plus tradeoffs, risk analysis, and retrieved source citations. The two model names must differ and must be among the supported models.

SDLC recommendation history reuses the existing `generated_recommendations` table; no database migration or schema change is needed. Each current LangGraph run is a new row marked with `scoring_method=langgraph_v2`. The existing JSON `alternatives` column stores the normal alternatives plus a private `_phase7` metadata object for scores, strengths, implementation notes, and retrieved sources. The recommendation endpoints unwrap that data. Previous LangGraph v1 recommendation rows remain stored but are not shown as current recommendations because their scorecards include retired candidates. The existing `/api/projects/{id}/analyze` and `/api/projects/{id}/recommendation` response schemas remain unchanged.

## Tests

Run from `backend/`:

```powershell
python -m pytest -q
```

Tests use isolated SQLite, temporary upload and Chroma directories, deterministic fake embeddings, and mocked Gemini/OpenAI providers. They do not require external API credentials or download the local embedding model. Coverage includes retrieval thresholds and filters, evaluation output, rank/precision checks, debug metadata, prompt assembly, source attribution, insufficient context, metrics logging, conversation persistence, local embedding provider selection, and Gemini/OpenAI chat provider selection, alongside existing document/vector tests.

## Phase 6 verification checklist

- [x] Questionnaire and project metadata are assembled into the prompt.
- [x] Existing vector retrieval supports top-k, score threshold, and metadata filters.
- [x] Retrieved source chunks are included in grounded prompts and returned in `sources`.
- [x] `evaluate-rag` exposes scores, selected context, rendered prompt, answer, and metrics.
- [x] `retrieval-debug` returns ranked text chunks and Chroma metadata without calling the LLM.
- [x] Metrics log retrieval time, prompt size/token estimate, and answer generation time/token estimate.
- [x] Insufficient context is stated explicitly in the answer prompt and tested.
- [x] Conversations and user/assistant messages persist in PostgreSQL.
- [x] All 38 backend tests pass with mocked embeddings, LLM providers, and SDLC workflow coverage.
- [ ] Live RAG responses require `GEMINI_API_KEY` by default; OpenAI chat remains available through `LLM_PROVIDER=openai` and `OPENAI_API_KEY`.
- [x] Phase 7 adds a LangGraph SDLC recommendation and comparison workflow; no multi-agent workflow or automatic final reports were added.

The LangGraph SDLC recommendation workflow is implemented. Multi-agent workflows remain out of scope.
