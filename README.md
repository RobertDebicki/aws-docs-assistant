# AWS Docs Assistant

A RAG chatbot that answers questions about the **AWS Well-Architected Framework** and cites the exact
document and page behind every answer — or refuses to answer when the documentation does not cover
the question.

**▶ Live demo:** https://aws-docs-assistant-4kvjd2bw7y2eyn7twrdxkj.streamlit.app/

---

## The problem

AWS Well-Architected documentation runs to hundreds of pages. Engineers rarely read it end to end —
they need a specific answer and they need to trust it enough to act on it.

A plain LLM answers confidently and sometimes wrongly, with no way to tell which is which. This
system answers **only from the source documents**, shows which document and page each answer came
from, and says so plainly when the documents do not contain the answer.

## What it actually does

Asked a question it can answer, it cites specific best-practice identifiers and page numbers:

> **Q: Co dokumentacja mówi o szyfrowaniu danych w spoczynku?**
>
> Dokumentacja mówi, że należy wymuszać szyfrowanie danych w spoczynku (SEC08-BP02 Enforce
> encryption at rest). […] Wspólne antywzorce to: niekorzystanie z konfiguracji encrypt-by-default,
> zapewnianie nadmiernie liberalnego dostępu do kluczy deszyfrujących […]
>
> *Źródła: Security Pillar s. 158, 159, 160*

Asked something outside the corpus, it refuses — **and shows no sources at all**:

> **Q: Jaka jest stolica Australii?**
>
> Nie znalazłem odpowiedzi na to pytanie w dokumentacji AWS Well-Architected.

That second case is the one that matters. A retrieval system always returns its *k* nearest chunks,
even for a question about Australian geography — so suppressing citations on refusal is deliberate.
Showing sources under "I don't know" would imply the answer rests on something.

## Architecture

```
PDF (AWS Well-Architected)
        │
        ▼
  chunking — 1500 chars, 200 overlap (pypdf + RecursiveCharacterTextSplitter)
        │
        ▼
  embeddings (Gemini, 768 dims) ──────► FAISS index (committed to this repo)
                                              │
user question ───────────────────────────► similarity search (k=4)
                                              │
                                              ▼
                                    prompt + context ──► Gemini Flash ──► answer + sources
```

## Stack

| Layer | Choice |
|---|---|
| Demo UI | Streamlit |
| API | FastAPI |
| LLM | Google Gemini Flash |
| Embeddings | Gemini embeddings, reduced to 768 dimensions |
| Vector store | FAISS (on disk, in-repo) |
| Observability | LangFuse |
| Hosting | Streamlit Community Cloud |

Every choice was constrained by one hard requirement: **zero hosting cost, no credit card.** That
constraint is why the deployment target changed mid-build — Hugging Face Spaces turned out to require
a paid plan for Docker Spaces. Full reasoning, including what was rejected and where each trade-off
stops being correct, is in [DECISIONS.md](DECISIONS.md).

## Layout

Retrieval logic is deliberately independent of any interface:

| File | Role |
|---|---|
| `rag.py` | Retrieval and answer generation. Imports no web framework |
| `ingest.py` | Builds the index. Run manually, downloads the PDFs itself |
| `config.py` | Key loading — `.env` locally, `st.secrets` in the cloud |
| `streamlit_app.py` | Demo interface (the deployed artifact) |
| `app.py` | The same logic as an HTTP API |
| `check_quality.py` | Manual quality check, including an out-of-scope question |

## Running locally

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # paste your real keys into .env
```

The index is committed, so the app runs immediately:

```bash
streamlit run streamlit_app.py     # demo interface
uvicorn app:app --reload           # or the API instead
python check_quality.py            # sanity-check answer quality
```

To rebuild the index from scratch (downloads ~5 MB of PDFs, takes about 9 minutes against the free
tier's rate limit):

```bash
python ingest.py
```

## Known limitations

- **Corpus is two pillars**, not the full framework — Security and Cost Optimization, 810 chunks.
  The 1002-page framework document was dropped to keep index construction under 10 minutes on the
  free tier.
- **No evaluation set.** Answer quality is checked by hand via `check_quality.py`. A proper eval
  harness with graded question/answer pairs is the first thing I would add with more time.
- **Chunk size is not tuned.** 1500/200 is a reasoned starting point, not a measured optimum.
- **The index goes stale** when AWS updates the documentation; refreshing it is a manual rerun.

## AI assistance disclosure

The implementation code in this repository was written with Claude Code (Anthropic) under my
direction and review. Architecture decisions, constraint definition, verification and testing are
mine, and are documented in [DECISIONS.md](DECISIONS.md).

Stating this is more useful than hiding it — the skill on display is designing and validating a
system, not typing it.
