"""
AWS Docs Assistant — RAG chatbot na dokumentacji AWS Well-Architected.

DZIEŃ 1: celowo minimalna wersja. Jedyne zadanie tego pliku dzisiaj to
udowodnić, że deploy na Hugging Face Spaces działa. Logika RAG wchodzi w dniu 2.
"""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Wczytuje .env przy starcie — dziala tylko lokalnie.
# Na Hugging Face Spaces pliku .env nie ma; tam zmienne wstrzykiwane sa
# przez panel Settings -> Secrets. load_dotenv() po prostu nic wtedy nie znajduje.
load_dotenv()

app = FastAPI(
    title="AWS Docs Assistant",
    description="RAG chatbot odpowiadajacy na pytania o AWS Well-Architected Framework",
    version="0.1.0",
)


#: Fragmenty wystepujace w .env.example. Jesli klucz je zawiera, to znaczy,
#: ze ktos skopiowal szablon i zapomnial podmienic wartosc.
PLACEHOLDER_MARKERY = ("tu-wklej", "xxxx", "zmien-mnie")


def klucz_ustawiony(nazwa: str) -> bool:
    """Czy zmienna srodowiskowa zawiera PRAWDZIWY klucz?

    Samo `bool(os.getenv(...))` nie wystarcza: placeholder ze skopiowanego
    .env.example to niepusty string, wiec przechodzi jako True i healthcheck
    klamie, ze konfiguracja jest kompletna. Odrzucamy wiec wartosci puste
    i takie, ktore wygladaja na nietkniety szablon.
    """
    wartosc = (os.getenv(nazwa) or "").strip()
    if not wartosc:
        return False
    return not any(marker in wartosc.lower() for marker in PLACEHOLDER_MARKERY)


@app.get("/health")
def health():
    """Healthcheck — sprawdza tez, czy zmienne srodowiskowe doszly na serwer.

    Zwraca WYLACZNIE informacje czy klucz jest ustawiony (True/False),
    nigdy jego wartosc. Logowanie sekretow to najczestszy wyciek w takich projektach.
    """
    konfiguracja = {
        "gemini_key_present": klucz_ustawiony("GOOGLE_API_KEY"),
        "langfuse_key_present": klucz_ustawiony("LANGFUSE_PUBLIC_KEY"),
    }
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
            "endpoints": {"health": "/health", "docs": "/docs"},
        }
    )
