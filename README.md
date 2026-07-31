---
title: AWS Docs Assistant
emoji: ☁️
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# AWS Docs Assistant

A RAG chatbot that answers questions about the **AWS Well-Architected Framework** and cites the exact
source document and page for every answer.

> 🚧 **Status: day 1 of a 7-day build.** Right now this is a deployed skeleton — the deployment
> pipeline works end to end before any AI logic exists. RAG lands on day 2.

**Live demo:** _(link added on day 3)_

---

## The problem

AWS Well-Architected documentation is hundreds of pages across six pillars. Engineers rarely read it
end to end — they need a specific answer ("what does the framework say about encrypting data at
rest?") and they need to trust it enough to act on it.

A plain LLM answers that question confidently and sometimes wrongly. This project answers it **only
from the source documents**, shows which document and page the answer came from, and says "I don't
know" when the documents don't cover it.

## Architecture

```
PDF (AWS Well-Architected)
        │
        ▼
  chunking (pypdf + text splitter)
        │
        ▼
  embeddings (Gemini) ──────► FAISS index (on disk)
                                    │
user question ─────────────────► retrieval (top-k)
                                    │
                                    ▼
                          prompt + context ──► Gemini Flash ──► answer + sources
                                    │
                                    ▼
                              LangFuse (tracing)
```

## Stack

| Layer | Choice |
|---|---|
| API | FastAPI |
| LLM | Google Gemini Flash |
| Embeddings | Gemini embeddings |
| Vector store | FAISS (local, on-disk) |
| Observability | LangFuse |
| Hosting | Hugging Face Spaces (Docker) |

Every choice here was constrained by one hard requirement: **zero hosting cost, no credit card.**
The reasoning — and what was rejected — is written up in [DECISIONS.md](DECISIONS.md).

## Running locally

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then paste your real keys into .env
uvicorn app:app --reload --port 8000
```

Open http://localhost:8000/health — it reports whether your keys were loaded, without ever printing
their values.

## AI assistance disclosure

The implementation code in this repository was written with Claude Code (Anthropic) under my
direction and review. Architecture decisions, constraint definition, verification and testing are
mine, and are documented in [DECISIONS.md](DECISIONS.md).

I take the view that stating this is more useful than hiding it — the skill being demonstrated here
is designing and validating a system, not typing it.
