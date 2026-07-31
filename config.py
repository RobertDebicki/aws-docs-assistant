"""Odczyt konfiguracji — dziala tak samo lokalnie i na Streamlit Cloud.

Problem: lokalnie klucze siedza w pliku `.env`, a na Streamlit Community Cloud
w panelu "Secrets" (dostepnym jako `st.secrets`). Zamiast rozsiewac po kodzie
warunki "jesli chmura, to tak, a jesli lokalnie, to inaczej", caly ten wybor
zamykamy w jednym miejscu.
"""

import os

from dotenv import load_dotenv

load_dotenv()

#: Fragmenty wystepujace w .env.example. Jesli klucz je zawiera, to znak,
#: ze ktos skopiowal szablon i zapomnial podmienic wartosc.
PLACEHOLDER_MARKERY = ("tu-wklej", "xxxx", "zmien-mnie")


def pobierz_klucz(nazwa: str) -> str | None:
    """Zwraca wartosc klucza z .env albo ze st.secrets (Streamlit Cloud).

    Kolejnosc: najpierw zmienne srodowiskowe, potem sekrety Streamlita.
    Import streamlita jest w srodku funkcji celowo — dzieki temu ten modul
    dziala rowniez w FastAPI i w skryptach, gdzie streamlita w ogole nie ma.
    """
    wartosc = os.getenv(nazwa)
    if wartosc:
        return wartosc

    try:
        import streamlit as st

        return st.secrets.get(nazwa)
    except Exception:
        # Brak streamlita albo brak pliku secrets — poza chmura to normalne.
        return None


def klucz_ustawiony(nazwa: str) -> bool:
    """Czy pod tym kluczem siedzi PRAWDZIWA wartosc?

    Samo sprawdzenie "czy niepuste" nie wystarcza: placeholder ze skopiowanego
    .env.example tez jest niepusty, wiec przechodzi jako poprawny i aplikacja
    zglasza gotowosc, majac bezuzyteczna konfiguracje.
    """
    wartosc = (pobierz_klucz(nazwa) or "").strip()
    if not wartosc:
        return False
    return not any(marker in wartosc.lower() for marker in PLACEHOLDER_MARKERY)


def stan_konfiguracji() -> dict[str, bool]:
    """Ktore klucze sa gotowe do uzycia."""
    return {
        "gemini": klucz_ustawiony("GOOGLE_API_KEY"),
        "langfuse": klucz_ustawiony("LANGFUSE_PUBLIC_KEY"),
    }
