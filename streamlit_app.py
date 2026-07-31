"""Interfejs demo — to ten plik uruchamia Streamlit Community Cloud.

Cała logika RAG siedzi w `rag.py`. Tutaj jest wyłącznie warstwa wizualna:
historia rozmowy, pole pytania i prezentacja źródeł.
"""

import streamlit as st

import rag
from config import config_status

st.set_page_config(page_title="AWS Docs Assistant", page_icon="☁️", layout="centered")

EXAMPLE_QUESTIONS = [
    "Co dokumentacja mówi o szyfrowaniu danych w spoczynku?",
    "Jak kontrolować koszty w architekturze AWS?",
    "Jakie są zasady zarządzania tożsamością i dostępem?",
]


@st.cache_resource(show_spinner="Wczytuję indeks dokumentacji...")
def load_index():
    """Wczytuje indeks raz na sesję serwera.

    Bez cache Streamlit przeładowywałby indeks przy KAŻDEJ interakcji
    użytkownika — skrypt wykonuje się od początku po każdym kliknięciu.
    """
    return rag.load_index()


def render_sources(sources: list[rag.Source]) -> None:
    """Źródła pod odpowiedzią — to one odróżniają RAG od zgadywania."""
    if not sources:
        return
    with st.expander(f"📄 Źródła ({len(sources)})"):
        for s in sources:
            st.markdown(f"**{s.document}**, strona {s.page}")
            st.caption(s.excerpt + "...")
            st.divider()


st.title("☁️ AWS Docs Assistant")
st.caption(
    "Odpowiada na pytania o AWS Well-Architected Framework wyłącznie na podstawie "
    "oficjalnej dokumentacji — z podaniem dokumentu i numeru strony."
)

status = config_status()

with st.sidebar:
    st.subheader("Stan systemu")
    st.write("Gemini API:", "✅" if status["gemini"] else "❌ brak klucza")
    st.write("LangFuse:", "✅" if status["langfuse"] else "⚪ opcjonalne")
    st.divider()
    st.subheader("Jak to działa")
    st.markdown(
        "1. Pytanie zamieniane jest na wektor liczb\n"
        "2. FAISS znajduje najbardziej podobne fragmenty dokumentacji\n"
        "3. Fragmenty trafiają do promptu jako jedyne źródło wiedzy\n"
        "4. Gemini odpowiada **tylko** na ich podstawie"
    )
    st.divider()
    st.caption("Indeks: Security Pillar + Cost Optimization Pillar (810 fragmentów)")

if not status["gemini"]:
    st.error(
        "Brak klucza GOOGLE_API_KEY. Lokalnie: uzupełnij `.env`. "
        "Na Streamlit Cloud: Settings → Secrets."
    )
    st.stop()

try:
    index = load_index()
except FileNotFoundError as e:
    st.error(str(e))
    st.stop()

if "history" not in st.session_state:
    st.session_state.history = []

# Przykłady pomagają pierwszemu użytkownikowi — puste pole czatu nie podpowiada,
# o co w ogóle można zapytać.
if not st.session_state.history:
    st.markdown("**Spróbuj zapytać:**")
    columns = st.columns(len(EXAMPLE_QUESTIONS))
    for column, example in zip(columns, EXAMPLE_QUESTIONS):
        if column.button(example, use_container_width=True):
            st.session_state.pending_question = example
            st.rerun()

for message in st.session_state.history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            render_sources(message["sources"])

question = st.chat_input("Zadaj pytanie o AWS Well-Architected...")
if not question:
    question = st.session_state.pop("pending_question", None)

if question:
    st.session_state.history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Szukam w dokumentacji..."):
            try:
                answer = rag.ask(index, question)
                st.markdown(answer.text)
                render_sources(answer.sources)
                st.session_state.history.append(
                    {
                        "role": "assistant",
                        "content": answer.text,
                        "sources": answer.sources,
                    }
                )
            except Exception as e:
                # Najczęstszy błąd w darmowym planie to 429 (limit zapytań).
                # Użytkownik ma zobaczyć, co się stało i co zrobić — nie stack trace.
                message = (
                    "Przekroczony limit zapytań do Gemini (darmowy plan). "
                    "Spróbuj ponownie za chwilę."
                    if "429" in str(e) or "quota" in str(e).lower()
                    else f"Błąd podczas odpowiadania: {type(e).__name__}"
                )
                st.error(message)
