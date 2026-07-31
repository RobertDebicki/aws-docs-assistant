"""
AWS Docs Assistant — warstwa API (FastAPI).

Interfejsem demo jest `streamlit_app.py` (hostowany na Streamlit Community Cloud).
Ten plik wystawia te sama logike jako HTTP API — do integracji i uruchomienia
lokalnego / z Dockerfile. Oba interfejsy czytaja konfiguracje z `config.py`
i beda korzystac z tego samego modulu RAG, bez duplikowania logiki.

DZIEN 1: celowo minimalna wersja — sam healthcheck.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from config import stan_konfiguracji

app = FastAPI(
    title="AWS Docs Assistant",
    description="RAG API odpowiadajace na pytania o AWS Well-Architected Framework",
    version="0.1.0",
)


@app.get("/health")
def health():
    """Healthcheck — potwierdza, ze aplikacja wstala i ma komplet kluczy.

    Zwraca WYLACZNIE informacje, czy klucz jest ustawiony (True/False),
    nigdy jego wartosc. Endpoint diagnostyczny wypluwajacy sekrety to
    najczestszy wyciek w tego typu projektach.
    """
    konfiguracja = stan_konfiguracji()
    return {
        "status": "ok" if all(konfiguracja.values()) else "missing_config",
        "stage": "dzien-1-szkielet",
        "config": konfiguracja,
    }


@app.get("/")
def root():
    return JSONResponse(
        {
            "name": "AWS Docs Assistant",
            "status": "W budowie — dzien 1: szkielet i deploy.",
            "demo": "Interfejs uzytkownika: streamlit_app.py",
            "endpoints": {"health": "/health", "docs": "/docs"},
        }
    )
