"""
AWS Docs Assistant — warstwa API (FastAPI).

Interfejsem demo jest `streamlit_app.py` (hostowany na Streamlit Community Cloud).
Ten plik wystawia tę samą logikę jako HTTP API — do integracji i uruchomienia
lokalnego. Oba interfejsy korzystają z `rag.py` i `config.py`, więc logika
wyszukiwania istnieje w jednym egzemplarzu.
"""

from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import rag
from config import config_status

app = FastAPI(
    title="AWS Docs Assistant",
    description="RAG API odpowiadające na pytania o AWS Well-Architected Framework",
    version="1.0.0",
)


class Question(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


@lru_cache(maxsize=1)
def get_index():
    """Wczytuje indeks raz i trzyma go w pamięci.

    Bez cache każde zapytanie HTTP odczytywałoby indeks z dysku od nowa.
    """
    return rag.load_index()


@app.get("/health")
def health():
    """Healthcheck — potwierdza, że aplikacja wstała i ma komplet kluczy.

    Zwraca WYŁĄCZNIE informację, czy klucz jest ustawiony (True/False),
    nigdy jego wartość. Endpoint diagnostyczny wypluwający sekrety to
    najczęstszy wyciek w tego typu projektach.
    """
    status = config_status()
    return {
        "status": "ok" if all(status.values()) else "missing_config",
        "config": status,
    }


@app.post("/chat")
def chat(payload: Question):
    """Zadaje pytanie do dokumentacji i zwraca odpowiedź wraz ze źródłami."""
    try:
        answer = rag.ask(get_index(), payload.question)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        # Limit darmowego planu Gemini to najczęstsza przyczyna błędu tutaj.
        # 429 przekazujemy dalej jako 429, żeby klient mógł ponowić z opóźnieniem.
        if "429" in str(e) or "quota" in str(e).lower():
            raise HTTPException(
                status_code=429,
                detail="Przekroczony limit zapytań do Gemini. Spróbuj ponownie za chwilę.",
            ) from e
        raise HTTPException(status_code=500, detail=f"Błąd: {type(e).__name__}") from e

    return {
        "answer": answer.text,
        "sources": [
            {"document": s.document, "page": s.page, "excerpt": s.excerpt}
            for s in answer.sources
        ],
    }


@app.get("/")
def root():
    return JSONResponse(
        {
            "name": "AWS Docs Assistant",
            "demo": "Interfejs użytkownika: streamlit_app.py",
            "endpoints": {"health": "/health", "chat": "POST /chat", "docs": "/docs"},
        }
    )
