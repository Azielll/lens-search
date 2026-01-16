# LensSearch

LensSearch is a full-stack project for AI-assisted code review. It indexes a GitHub repository, retrieves relevant code patterns, and uses that context to improve PR review quality.

## What’s in this repo

- `backend/` — FastAPI services, GitHub integration, and RAG indexing/retrieval.
- `frontend/` — Next.js UI for search and review workflows.

## High-level workflow

1. Index a repository into a vector database (RAG index).
2. Collect PR context from GitHub (diffs, metadata).
3. Retrieve similar code patterns from the index.
4. Generate review guidance using the retrieved context.

## Quick start (local)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Environment variables

Set these for backend features:

- `GITHUB_TOKEN` — GitHub API access
- `GEMINI_API_KEY` — Embeddings for RAG

## Notes

- The root of the RAG index lives under `backend/data/` by default.
- See `backend/AI_AGENT_PLAN.md` for deeper architecture details.
