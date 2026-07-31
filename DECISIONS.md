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

## 3. Hugging Face Spaces instead of AWS Lambda

**Chosen:** Hugging Face Spaces, Docker SDK, CPU Basic.

**Rejected:** AWS Lambda + API Gateway, Render, Railway.

Lambda would have been the more on-brand choice. Two things ruled it out for a one-week build: the
dependency bundle (LangChain plus FAISS) pushes against Lambda's package size limits and needs
layers to work around, and the account still needs a card even inside the free tier. Spaces gives
2 vCPU and 16 GB RAM for free with a Dockerfile I control.

**Trade-off accepted:** free Spaces **sleep after 48 hours of inactivity** and take roughly 30
seconds to wake. For a portfolio link that a recruiter might open at any time, that is a real
problem — a cold link reads as a broken link. Mitigated with a scheduled GitHub Actions workflow
that pings the Space once a day, which keeps it warm at no cost.

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
