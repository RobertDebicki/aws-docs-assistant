"""Logika RAG — wyszukiwanie w dokumentacji i generowanie odpowiedzi.

Ten moduł nie wie nic o interfejsie. Nie importuje streamlita ani fastapi,
dzięki czemu korzysta z niego zarówno `streamlit_app.py`, jak i `app.py`,
a testować go można zwykłym skryptem.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from config import get_key

INDEX_DIR = Path("index")

EMBEDDING_MODEL = "models/gemini-embedding-001"
#: MUSI być identyczny jak w ingest.py. Wektor pytania i wektory fragmentów
#: muszą mieć tę samą długość, inaczej porównanie jest matematycznie niemożliwe.
EMBEDDING_DIMENSIONS = 768

#: Flash zamiast Pro: w darmowym planie Gemini modele Pro nie są dostępne,
#: a do odpowiadania na podstawie podanego kontekstu Flash w zupełności wystarcza.
LLM_MODEL = "gemini-2.5-flash"

#: Ile fragmentów trafia do promptu. Za mało — brak kontekstu; za dużo — model
#: gubi się w szumie i rośnie zużycie limitu tokenów.
RETRIEVED_CHUNKS = 4

#: Nazwy kluczy w metadanych fragmentów — MUSZĄ być identyczne jak w ingest.py.
#: To nie są nazwy w kodzie, tylko dane zapisane wewnątrz indeksu: zmiana tych
#: napisów unieważnia zbudowany indeks i wymusza jego przeliczenie od zera.
METADATA_SOURCE = "zrodlo"
METADATA_PAGE = "strona"

#: Dokładna treść odmowy. Jest w jednym miejscu, bo pełni dwie role naraz:
#: instruuje model, co ma napisać, i pozwala nam ROZPOZNAĆ, że odmówił.
REFUSAL_MESSAGE = (
    "Nie znalazłem odpowiedzi na to pytanie w dokumentacji AWS Well-Architected."
)

PROMPT_TEMPLATE = """Jesteś asystentem odpowiadającym na pytania o AWS Well-Architected Framework.

ZASADY — przestrzegaj ich bezwzględnie:
1. Odpowiadaj WYŁĄCZNIE na podstawie fragmentów dokumentacji poniżej.
2. Jeśli fragmenty nie zawierają odpowiedzi, napisz dosłownie:
   "Nie znalazłem odpowiedzi na to pytanie w dokumentacji AWS Well-Architected."
   Nie uzupełniaj takiej odpowiedzi wiedzą własną.
3. Nie zmyślaj nazw usług, liczb ani zaleceń, których nie ma we fragmentach.
4. Odpowiadaj po polsku, zwięźle i konkretnie, nawet gdy dokumentacja jest po angielsku.
5. Terminy techniczne AWS zostaw w oryginale (np. "Security Pillar", "IAM").

FRAGMENTY DOKUMENTACJI:
{context}

PYTANIE:
{question}

ODPOWIEDŹ:"""


@dataclass
class Source:
    """Fragment dokumentacji użyty do odpowiedzi."""

    document: str
    page: int
    excerpt: str


@dataclass
class Answer:
    """Wynik zapytania: treść plus źródła, na których się opiera."""

    text: str
    sources: list[Source]


def _export_key_to_environment() -> None:
    """LangChain czyta klucz ze zmiennej środowiskowej.

    Lokalnie trafia tam z `.env`, ale na Streamlit Cloud siedzi w `st.secrets`
    i sam z siebie do środowiska nie trafi — trzeba go tam przepisać.
    """
    key = get_key("GOOGLE_API_KEY")
    if key:
        os.environ["GOOGLE_API_KEY"] = key


def load_index() -> FAISS:
    """Wczytuje zbudowany wcześniej indeks FAISS z dysku.

    Indeks powstaje raz, skryptem `ingest.py`, i leży w repo. Aplikacja nigdy
    go nie przelicza — inaczej każde uruchomienie kosztowałoby setki zapytań
    do API i kilka minut czekania użytkownika.
    """
    if not INDEX_DIR.exists():
        raise FileNotFoundError(
            f"Brak indeksu w katalogu '{INDEX_DIR}'. Uruchom najpierw: python ingest.py"
        )

    _export_key_to_environment()
    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        output_dimensionality=EMBEDDING_DIMENSIONS,
    )

    # allow_dangerous_deserialization: FAISS zapisuje metadane przez pickle,
    # który potrafi wykonać kod przy odczycie. Włączamy to świadomie, bo indeks
    # pochodzi z naszego własnego repo. Przy pliku z zewnątrz byłoby to ryzykowne.
    return FAISS.load_local(
        str(INDEX_DIR),
        embeddings,
        allow_dangerous_deserialization=True,
    )


def _build_context(documents) -> str:
    """Skleja fragmenty w jeden blok tekstu, każdy podpisany źródłem."""
    parts = []
    for i, doc in enumerate(documents, start=1):
        source = doc.metadata.get(METADATA_SOURCE, "nieznany dokument")
        page = doc.metadata.get(METADATA_PAGE, "?")
        parts.append(f"[Fragment {i} — {source}, strona {page}]\n{doc.page_content}")
    return "\n\n".join(parts)


def ask(index: FAISS, question: str) -> Answer:
    """Pełna ścieżka RAG: wyszukaj fragmenty, zbuduj prompt, zapytaj model."""
    _export_key_to_environment()

    documents = index.similarity_search(question, k=RETRIEVED_CHUNKS)

    if not documents:
        return Answer(text=REFUSAL_MESSAGE, sources=[])

    prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    # temperature=0: przy odpowiadaniu z dokumentu chcemy powtarzalności,
    # a nie kreatywności. To samo pytanie ma dawać tę samą odpowiedź.
    model = ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=0)

    chain = prompt | model
    result = chain.invoke(
        {"context": _build_context(documents), "question": question}
    )

    text = result.content

    # Gdy model odmówił odpowiedzi, NIE pokazujemy źródeł.
    # FAISS zawsze zwraca k najbliższych fragmentów — nawet dla pytania o stolicę
    # Australii znajdzie cztery "najmniej odległe" kawałki dokumentacji AWS.
    # Wyświetlenie ich pod komunikatem "nie znalazłem odpowiedzi" sugerowałoby,
    # że odpowiedź jednak z czegoś wynika. Cytowanie ma znaczyć: "to jest podstawa
    # tej odpowiedzi" — przy odmowie żadnej podstawy nie ma.
    if REFUSAL_MESSAGE.lower() in text.lower():
        return Answer(text=text, sources=[])

    sources = [
        Source(
            document=d.metadata.get(METADATA_SOURCE, "nieznany"),
            page=d.metadata.get(METADATA_PAGE, 0),
            excerpt=d.page_content[:300],
        )
        for d in documents
    ]

    return Answer(text=text, sources=sources)
