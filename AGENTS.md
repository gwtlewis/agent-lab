# AGENTS.md — Agent Collaboration Guide

> This file defines how AI agents (Copilot, Claude, GPT, etc.) should work in this repository.
> **Read it fully before taking any action.**

---

## ⚠️ Golden Rule: Never Assume — Always Ask

If anything is unclear about the requirement, the existing code, or the intended behavior:

**STOP. Ask the human to clarify. Do not guess.**

Examples of things you must ask about rather than assume:
- The intended scope of a change ("does this apply to all LLM providers or just Ollama?")
- Expected behavior for edge cases or error conditions
- Whether a breaking change is acceptable
- Which part of the system is "source of truth" when two places conflict
- Whether a new dependency is allowed
- Performance or scalability expectations

If you proceed with an assumption and it turns out to be wrong, you may cause cascading damage that is harder to undo than asking a question was.

---

## Project Overview

**Agent Lab** is a production-ready AI-powered semantic document search system built with:

| Layer | Technology |
|-------|-----------|
| LLM Orchestration | LangChain (multi-provider: Ollama / OpenAI) |
| Web Server | FastAPI + Uvicorn (WebSocket streaming) |
| Vector Database | PostgreSQL 17.9 + pgvector (768-dim embeddings) |
| PDF Ingestion | pypdf + LangChain text splitters |
| Testing | pytest, pytest-asyncio, pytest-playwright |
| Infrastructure | Docker + docker-compose |

**Entry points:**
- `agent/core/agent.py` — base LangChain agent
- `agent/core/agent_with_rag.py` — RAG-enhanced agent
- `agent/server/web_server.py` — FastAPI web server
- `agent/rag/pdf_ingester.py` — PDF chunking & embedding pipeline
- `agent/rag/rag_retriever.py` — vector similarity search

**Documentation:** all living docs are in `docs/`. Start with `docs/INDEX.md`.

---

## Standard Feature Workflow

Every new feature or meaningful change must follow these six phases **in order**. Do not skip or reorder them.

---

### Phase 1 — Understand the Requirement

Before writing a single line of code:

1. Read the relevant parts of `docs/` and any files mentioned by the human.
2. Identify every component and file that will be affected.
3. Write out your understanding of what the feature should do in plain language.
4. **Ask the human to confirm your understanding is correct.**
5. If any behavior, constraint, or scope is ambiguous — **ask, do not assume**.

Questions to always resolve before proceeding:
- What problem does this solve? What is the user-visible outcome?
- What are the acceptance criteria? How will success be measured?
- What is explicitly out of scope?
- Are there performance, security, or backwards-compatibility constraints?
- Does this touch the DB schema? The public API? The streaming protocol?

---

### Phase 2 — Write an Implementation Spec

Produce a short written spec and **present it to the human for review before coding**.

The spec must include:

```
## Implementation Spec: <Feature Name>

### Problem Statement
One paragraph describing the problem this solves.

### Proposed Solution
High-level approach: which components change and how.

### Files to Create / Modify
- agent/foo.py — add class Bar that ...
- agent/server/web_server.py — add endpoint POST /foo ...
- init-scripts/01-vectors.sql — add column ...
- docs/AGENT.md — document new endpoint

### API / Interface Changes
Describe any new or changed public interfaces (function signatures, REST endpoints,
WebSocket messages, DB schema, environment variables).

### Breaking Changes
List anything that may break existing callers. State explicitly if there are none.

### Open Questions
List any decisions still to be made before coding begins.
```

**Do not begin Phase 3 until the human has approved the spec.**

---

### Phase 3 — Write Tests First (TDD)

Write tests before (or alongside) implementing the feature. Tests live in `agent/tests/test_*.py`.

#### Guiding principles
- Every new function / class / endpoint needs at least one test.
- Cover the happy path **and** expected failure / edge-case paths.
- Use `pytest` and `pytest-asyncio` for async code.
- Use `pytest-playwright` only for UI-level flows.
- Mock external services (LLM providers, PostgreSQL) where integration is not the point.
- Name test functions descriptively: `test_<what>_<condition>_<expected>`.

#### Run the full regression suite before and after your change

```bash
cd agent
.venv/bin/python -m pytest -v 2>&1 | tail -20
```

All pre-existing tests must continue to pass. If a test legitimately needs to change because the interface changed, document why in the spec and get human approval before modifying it.

---

### Phase 4 — Implement

Write the code. Follow these conventions:

- **Python style**: PEP 8, type hints on all public functions.
- **JavaScript style**: ES2020+, `"use strict"`, prefer `const`/`let` over `var`, `===` over `==`.
- **Docstrings**: Google-style on all public Python classes and functions.
- **JS comments**: JSDoc on exported functions; inline comments for non-obvious logic.
- **Logging**: use `logging` (already used in the codebase), not `print`.
- **Environment config**: use `.env` + `python-dotenv`; never hard-code secrets.
- **DB changes**: update `init-scripts/01-vectors.sql`; document migration steps if needed.
- **No new dependencies** without asking the human first.

Keep changes surgical — only modify what is necessary to implement the spec. Do not refactor unrelated code in the same PR/commit.

---

### Phase 5 — Code Quality Checks

Run linting and static analysis before declaring the implementation done.

For frontend/UI changes, add or update `pytest-playwright` tests in `agent/tests/test_ui_headless.py` so key UX flows are regression-tested automatically (not only manually).

---

#### Python linting (install once if missing)

```bash
pip install flake8 pylint
```

```bash
# PEP 8 style
cd agent
../.venv/bin/flake8 core/ providers/ rag/ server/ scripts/ --max-line-length=120

# Deeper static analysis
../.venv/bin/pylint core/ providers/ rag/ server/ scripts/ --disable=C0114,C0115,C0116 --max-line-length=120
```

Fix all **errors** (E-level flake8, pylint score < 7). Warnings (W-level) should be reviewed and addressed unless there is a documented reason to suppress them.

#### Python type checking (optional but encouraged)

```bash
pip install mypy
mypy agent/core/ agent/providers/ agent/rag/ agent/server/ --ignore-missing-imports
```

---

#### JavaScript linting (install once if missing)

```bash
npm install -g eslint
```

Run against all frontend JS files:

```bash
eslint agent/static/**/*.js --env browser,es2020 --parser-options=ecmaVersion:2020
```

For a one-off check without a config file:

```bash
npx eslint agent/static/app.js --env browser,es2020 --parser-options=ecmaVersion:2020 \
  --rule '{"no-unused-vars": "warn", "no-undef": "error", "eqeqeq": "error"}'
```

If the project gains a `tsconfig.json` or TypeScript files (`.ts`/`.tsx`), use `tsc --noEmit` for type checking:

```bash
npx tsc --noEmit
```

Fix all **errors** (no-undef, eqeqeq violations, syntax errors). Warnings (no-unused-vars) should be reviewed.

---

#### Full regression

```bash
cd agent
.venv/bin/python -m pytest -v
```

#### Frontend regression subset (recommended for UI work)

```bash
cd agent
.venv/bin/python -m pytest -v test_ui_headless.py
```

For UI changes, this command is the minimum acceptance gate before marking work complete.

**All tests must pass before moving to Phase 6.** If tests fail, fix them — do not skip or comment them out.

---

### Phase 6 — Update Documentation

Update `docs/` to reflect every change visible to humans or other developers.
For major code changes or new features, make sure the docs describe the new behavior,
any user-facing workflow changes, and any developer-facing conventions or setup steps.

| Type of change | Docs to update |
|---------------|----------------|
| New REST endpoint or WebSocket message | `docs/AGENT.md` |
| New CLI command or flag | `docs/CLI_USAGE.md` |
| UI change | `docs/WEB_UI.md` |
| Architecture / component addition | `docs/ARCHITECTURE.md` |
| New test suite or testing strategy | `docs/XVA_RAG_TESTING.md` |
| Anything affecting first-run setup | `docs/QUICKSTART.md` |
| Project-wide status | `docs/PROJECT_STATUS.md` |
| Any of the above | `docs/INDEX.md` (update links / quick-reference if needed) |

Then ask the human:

> **"Should I update AGENTS.md to reflect any new conventions, constraints, or tools introduced by this feature?"**

AGENTS.md should evolve as the project evolves. Keep it accurate.

---

## Quick Reference: Phase Checklist

```
[ ] Phase 1 — Requirements confirmed by human
[ ] Phase 2 — Spec written and approved by human
[ ] Phase 3 — Tests written; regression baseline captured
[ ] Phase 4 — Implementation complete
[ ] Phase 5 — Linting clean; all tests pass
[ ] Phase 6 — Docs updated; human asked about AGENTS.md
```

---

## Repository Layout

```
agent-lab/
├── agent/
│   ├── core/                 # Agent classes + event model
│   │   ├── agent.py          # Base LangChain agent
│   │   ├── agent_with_rag.py # RAG-enhanced agent
│   │   └── event_model.py    # Streaming event schema
│   ├── providers/            # LLM provider adapters
│   │   ├── llm_providers.py  # Provider abstraction + factory
│   │   └── ollama_utils.py   # Ollama host helpers
│   ├── rag/                  # RAG pipeline
│   │   ├── pdf_ingester.py   # PDF → chunks → embeddings
│   │   └── rag_retriever.py  # Vector similarity search
│   ├── server/               # FastAPI + WebSocket server
│   │   └── web_server.py
│   ├── scripts/              # CLI entry points
│   │   ├── ingest_pdf.py     # PDF ingestion CLI
│   │   └── demo_xva_rag.py   # Demo script
│   ├── tests/                # All test files (pytest)
│   │   ├── fixtures/
│   │   │   └── test_xva_10pages.pdf
│   │   └── test_*.py
│   ├── static/               # Frontend assets
│   ├── conftest.py           # Pytest path setup
│   ├── pytest.ini            # Pytest configuration
│   ├── requirements.txt      # Python dependencies
│   └── .env                  # Local config (not committed)
├── docs/                     # All living documentation
│   └── INDEX.md              # Start here
├── init-scripts/
│   └── 01-vectors.sql        # DB schema initialization
├── Dockerfile                # pgvector base image
├── docker-compose.yml        # DB service definition
├── start.sh                  # Web server launcher
└── AGENTS.md                 # ← You are here
```

---

## Running the Stack

```bash
# 1. Start the database
docker-compose up -d

# 2. Activate the virtual environment
source agent/.venv/bin/activate   # or: cd agent && source .venv/bin/activate

# 3. Run all tests
python -m pytest -v

# 4. Start the web server
./start.sh

# 5. Ingest a PDF
python agent/scripts/ingest_pdf.py --file /path/to/document.pdf
```

---

## What Agents Must NOT Do

- ❌ Commit secrets, credentials, or API keys to any file
- ❌ Modify `.env` contents (read it, document its variables, but do not change values)
- ❌ Delete or rename existing test files without explicit human approval
- ❌ Add new Python packages to `requirements.txt` without asking first
- ❌ Alter the DB schema without updating `init-scripts/01-vectors.sql` and documenting the migration
- ❌ Skip the spec review (Phase 2) — even for "small" changes
- ❌ Mark a task done while tests are failing
- ❌ Make assumptions when uncertain — always ask
