# Architecture decisions

Why this system looks the way it does — including what was deliberately rejected.

Every decision below was made under one hard constraint: **the demo must be publicly reachable at
zero cost, with no credit card on file.** That constraint drove almost everything.

---

## 1. Gemini Flash instead of AWS Bedrock

**Chosen:** Google Gemini Flash via `langchain-google-genai`.

**Rejected:** AWS Bedrock (Claude / Titan).

Bedrock is the natural fit for the subject matter and for the kind of work I want to do. It is not
in the AWS Free Tier — it bills per token from the first request and requires a card on file.
Gemini's free tier serves Flash models without a card.

**Trade-off accepted:** the free tier is rate limited (roughly 10 requests/minute, a few hundred to
~1500 per day). For a portfolio demo that is comfortable; for production it would not be. The API
returns HTTP 429 when exceeded, and the app surfaces that as a readable message instead of a stack
trace.

**What I would change with a budget:** move to Bedrock, keeping the LangChain abstraction so the
swap is a config change rather than a rewrite. This is the main reason the LLM is accessed through
LangChain rather than the Gemini SDK directly.

---

## 2. FAISS instead of a managed vector database

**Chosen:** FAISS, persisted to disk inside the container.

**Rejected:** Pinecone, Qdrant Cloud, Supabase pgvector — all of which have usable free tiers.

The document set is small (a handful of PDFs, low thousands of chunks). At that size a managed
vector database adds a network hop, a second set of credentials and an external dependency that can
be deprecated or rate limited, in exchange for scaling headroom I do not need.

**Trade-off accepted:** the index lives in the container, so it is rebuilt on deploy and cannot be
shared between services or updated without a redeploy. That is the correct trade at this size and
the wrong one past roughly a million vectors.

---

## 3. Streamlit Community Cloud — after Hugging Face Spaces failed at deploy time

**Chosen:** Streamlit Community Cloud.

**Rejected:** Hugging Face Spaces (original plan), AWS Lambda + API Gateway, Render.

Lambda was ruled out early: the dependency bundle (LangChain plus FAISS) pushes against Lambda's
package size limits and needs layers to work around, and the account needs a card even inside the
free tier.

Hugging Face Spaces was the original choice — 2 vCPU and 16 GB RAM, free, with a Dockerfile I
control. **It failed at deploy time.** Creating the Space returned `402 Payment Required`:

> Static Spaces are free for everyone, but hosting Gradio and Docker Spaces on free cpu-basic
> requires a PRO subscription.

The free tier now covers static Spaces only. Python backends need a paid plan, which breaks the
zero-cost constraint this project is built on.

Render was the closest alternative and needs no card, but its free web services sleep after 15
minutes and take roughly 50 seconds to wake. A portfolio link that hangs for a minute reads as a
broken link, so that trade was worse than Streamlit's.

**Trade-off accepted:** Streamlit Community Cloud allows 3 apps, caps memory at 1 GB and sleeps
after 12 quiet hours. The 1 GB cap is the constraint that matters — it is the reason embeddings are
computed through the Gemini API rather than by running a local sentence-transformers model, which
would not fit alongside the index.

**Why this is written down:** the deployment target changed *because deploying on day 1 exposed the
problem while there were still six days left*. Had the deploy been left until the end, this would
have surfaced with finished code and no time to react. This is the strongest argument for shipping
an empty skeleton first.

---

## 3b. The RAG logic is separate from the interface

Moving to Streamlit forced a decision that improved the design: **the retrieval logic lives in its
own module and knows nothing about the UI.**

- `config.py` — reads keys from `.env` locally and from `st.secrets` in the cloud
- `streamlit_app.py` — the demo interface, deployed publicly
- `app.py` — the same logic exposed as a FastAPI HTTP API, for integration and local use

The `Dockerfile` is kept and still works for running the API locally. It is no longer the deployment
path.

The point is that swapping the interface — or the host, again — does not touch the retrieval code.

---

## 4. Full dependency set installed on day 1

The day-1 deployment exposes only a `/health` endpoint, but `requirements.txt` already pins the
whole RAG stack including `faiss-cpu`.

This is deliberate. The point of deploying on day 1 is to prove the *real* pipeline works. A
skeleton that only installs FastAPI proves nothing about whether the heavy native dependencies
build on the target platform — and finding that out on day 6 is how a one-week build fails.

---

## 5. Secrets never leave the environment

`.env` holds real keys and is gitignored. `.env.example` contains placeholders only and is
committed. The `/health` endpoint reports whether a key is **present** as a boolean and never
returns or logs its value.

This is a direct response to a mistake I made earlier in this repo's history: a real Airtable token
was committed to a `.env.example` file and had to be regenerated. The rule that came out of it —
`.env` is secrets, `.env.example` is a template — is now applied from the first commit of every
project.

---

## Open questions

- Chunk size and overlap are not yet tuned. Current values are a starting point, not a measured
  optimum.
- There is no evaluation set. Retrieval quality is currently judged by hand on a small set of
  questions, including questions the documents cannot answer. A proper eval harness is the first
  thing I would add with more time.
