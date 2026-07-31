"""Odczyt konfiguracji — działa tak samo lokalnie i na Streamlit Cloud.

Problem: lokalnie klucze siedzą w pliku `.env`, a na Streamlit Community Cloud
w panelu "Secrets" (dostępnym jako `st.secrets`). Zamiast rozsiewać po kodzie
warunki "jeśli chmura, to tak, a jeśli lokalnie, to inaczej", cały ten wybór
zamykamy w jednym miejscu.
"""

import os

from dotenv import load_dotenv

load_dotenv()

#: Fragmenty występujące w .env.example. Jeśli klucz je zawiera, to znak,
#: że ktoś skopiował szablon i zapomniał podmienić wartość.
PLACEHOLDER_MARKERS = ("tu-wklej", "xxxx", "zmien-mnie")


def get_key(name: str) -> str | None:
    """Zwraca wartość klucza z .env albo ze st.secrets (Streamlit Cloud).

    Kolejność: najpierw zmienne środowiskowe, potem sekrety Streamlita.
    Import streamlita jest w środku funkcji celowo — dzięki temu ten moduł
    działa również w FastAPI i w skryptach, gdzie streamlita w ogóle nie ma.
    """
    value = os.getenv(name)
    if value:
        return value

    try:
        import streamlit as st

        return st.secrets.get(name)
    except Exception:
        # Brak streamlita albo brak pliku secrets — poza chmurą to normalne.
        return None


def is_key_set(name: str) -> bool:
    """Czy pod tym kluczem siedzi PRAWDZIWA wartość?

    Samo sprawdzenie "czy niepuste" nie wystarcza: placeholder ze skopiowanego
    .env.example też jest niepusty, więc przechodzi jako poprawny i aplikacja
    zgłasza gotowość, mając bezużyteczną konfigurację.
    """
    value = (get_key(name) or "").strip()
    if not value:
        return False
    return not any(marker in value.lower() for marker in PLACEHOLDER_MARKERS)


def config_status() -> dict[str, bool]:
    """Które klucze są gotowe do użycia."""
    return {
        "gemini": is_key_set("GOOGLE_API_KEY"),
        "langfuse": is_key_set("LANGFUSE_PUBLIC_KEY"),
    }
