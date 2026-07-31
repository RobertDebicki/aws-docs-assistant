"""Budowa indeksu wektorowego z dokumentacji AWS Well-Architected.

Uruchamiany RECZNIE i LOKALNIE, nie w chmurze:

    python ingest.py

Powod: zbudowanie indeksu to kilkaset zapytan do API o embeddingi. Gdyby robila
to aplikacja przy starcie, kazde przebudzenie uspionego Streamlita zjadaloby
darmowy limit i kazalo uzytkownikowi czekac kilka minut. Zamiast tego indeks
powstaje raz, ladujemy go do repo, a aplikacja tylko go odczytuje.

Skrypt sam pobiera PDF-y, jesli ich nie ma — dzieki temu kazdy, kto sklonuje
repo, odtworzy indeks jedna komenda.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import get_key, is_key_set
from rag import METADATA_PAGE, METADATA_SOURCE

PDF_DIR = Path("data/pdfs")
INDEX_DIR = Path("index")

#: Publiczna dokumentacja AWS Well-Architected. Klucz slownika trafia do
#: metadanych kazdego fragmentu, zeby odpowiedz mogla wskazac zrodlo po nazwie.
#:
#: Glowny "Framework" (1002 strony, 2257 fragmentow) zostal SWIADOMIE pominiety.
#: Darmowy plan Gemini pozwala na 100 embeddingow na minute, wiec dolozenie go
#: wydluzyloby budowe indeksu z ~8 do ponad 30 minut. Dwa filary to spojny
#: tematycznie zestaw, w zupelnosci wystarczajacy dla demo.
DOCUMENTS = {
    "Security Pillar": "https://docs.aws.amazon.com/pdfs/wellarchitected/latest/security-pillar/wellarchitected-security-pillar.pdf",
    "Cost Optimization Pillar": "https://docs.aws.amazon.com/pdfs/wellarchitected/latest/cost-optimization-pillar/wellarchitected-cost-optimization-pillar.pdf",
}

#: ~1500 znakow to okolo 3 akapity — dosc, zeby fragment byl zrozumialy sam
#: z siebie, i na tyle malo, zeby do promptu zmiescilo sie kilka fragmentow.
#: Zakladka 200 znakow chroni przed przecieciem zdania w polowie: koniec jednego
#: fragmentu powtarza sie na poczatku nastepnego.
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200

#: Darmowy plan Gemini: 100 zapytan o embedding na minute (kazdy fragment to
#: osobne zapytanie). Bierzemy 90 z zapasem na zaokraglenia po stronie API.
BATCH_SIZE = 90
PAUSE_BETWEEN_BATCHES = 62  # sekundy — okno limitu to minuta, dokladamy margines

#: Gemini zwraca domyslnie 3072 liczby na fragment. Model pozwala skrocic wektor
#: bez przebudowy (Matryoshka), a 768 wymiarow zajmuje 4x mniej pamieci.
#: Przy limicie 1 GB na Streamlit Community Cloud to roznica miedzy
#: "dziala" a "aplikacja ubita przez brak pamieci".
EMBEDDING_DIMENSIONS = 768
EMBEDDING_MODEL = "models/gemini-embedding-001"


def download_pdfs() -> list[tuple[str, Path]]:
    """Sciaga brakujace PDF-y. Zwraca pary (nazwa dokumentu, sciezka)."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    files = []

    for name, url in DOCUMENTS.items():
        path = PDF_DIR / (url.rsplit("/", 1)[-1])
        if path.exists():
            print(f"  [jest]    {name}")
        else:
            print(f"  [pobieram] {name} ...", end=" ", flush=True)
            response = requests.get(url, timeout=120)
            response.raise_for_status()
            path.write_bytes(response.content)
            print(f"{len(response.content) / 1_000_000:.1f} MB")
        files.append((name, path))

    return files


def load_and_split(files: list[tuple[str, Path]]):
    """PDF -> lista fragmentow z metadanymi (zrodlo + numer strony)."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        # Kolejnosc ma znaczenie: tnij najpierw na akapitach, potem na zdaniach,
        # a dopiero w ostatecznosci w srodku slowa.
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks_all = []
    for name, path in files:
        pages = PyPDFLoader(str(path)).load()
        chunks = splitter.split_documents(pages)

        for chunk in chunks:
            # PyPDF liczy strony od zera, a czytelnik patrzy na numer wydrukowany
            # w dokumencie — bez tego +1 cytowania bylyby przesuniete o jedna strone.
            chunk.metadata[METADATA_SOURCE] = name
            chunk.metadata[METADATA_PAGE] = chunk.metadata.get("page", 0) + 1

        print(f"  {name}: {len(pages)} stron -> {len(chunks)} fragmentow")
        chunks_all.extend(chunks)

    return chunks_all


def build_index(chunks) -> None:
    """Liczy embeddingi paczkami i zapisuje indeks FAISS na dysk.

    Dlaczego paczkami, a nie jednym `FAISS.from_documents`:
    darmowy plan pozwala na 100 embeddingow na minute, a jedno zbiorcze
    wywolanie probuje policzyc wszystko naraz i konczy sie bledem 429.

    Po kazdej paczce indeks jest zapisywany. Gdy cokolwiek przerwie prace
    (limit, zerwane polaczenie), dotychczasowy postep zostaje na dysku.
    """
    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        output_dimensionality=EMBEDDING_DIMENSIONS,
    )

    batches = [
        chunks[i : i + BATCH_SIZE]
        for i in range(0, len(chunks), BATCH_SIZE)
    ]
    minutes = (len(batches) - 1) * PAUSE_BETWEEN_BATCHES / 60

    print(f"\nLicze embeddingi dla {len(chunks)} fragmentow")
    print(f"Paczek: {len(batches)} po {BATCH_SIZE} — szacowany czas ~{minutes:.0f} min")
    print("(limit darmowego planu: 100 embeddingow/min)\n")

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    start = time.time()
    index: FAISS | None = None

    for number, batch in enumerate(batches, start=1):
        if index is None:
            index = FAISS.from_documents(batch, embeddings)
        else:
            index.add_documents(batch)

        index.save_local(str(INDEX_DIR))
        print(f"  paczka {number}/{len(batches)} gotowa ({number * BATCH_SIZE} fragmentow)")

        if number < len(batches):
            time.sleep(PAUSE_BETWEEN_BATCHES)

    elapsed = time.time() - start
    size_mb = sum(p.stat().st_size for p in INDEX_DIR.glob("*")) / 1_000_000
    print(f"\nGotowe w {elapsed / 60:.1f} min. Indeks: {INDEX_DIR}/ ({size_mb:.1f} MB)")


def main() -> int:
    if not is_key_set("GOOGLE_API_KEY"):
        print("BLAD: brak GOOGLE_API_KEY. Uzupelnij plik .env.", file=sys.stderr)
        return 1

    # LangChain czyta klucz ze zmiennej srodowiskowej — upewniamy sie, ze tam jest,
    # niezaleznie od tego, czy przyszedl z .env, czy ze st.secrets.
    import os

    os.environ["GOOGLE_API_KEY"] = get_key("GOOGLE_API_KEY") or ""

    print("1/3 Pobieranie dokumentow")
    files = download_pdfs()

    print("\n2/3 Wczytywanie i dzielenie na fragmenty")
    chunks = load_and_split(files)

    print("\n3/3 Budowa indeksu wektorowego")
    build_index(chunks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
