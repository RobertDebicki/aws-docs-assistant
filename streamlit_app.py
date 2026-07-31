"""Interfejs demo — to ten plik uruchamia Streamlit Community Cloud.

DZIEN 1: celowo bez logiki RAG. Zadaniem tej wersji jest wylacznie potwierdzic,
ze deploy dziala i ze sekrety doszly do chmury. Wyszukiwanie i odpowiedzi
wchodza w dniu 2.
"""

import streamlit as st

from config import stan_konfiguracji

st.set_page_config(page_title="AWS Docs Assistant", page_icon="☁️", layout="centered")

st.title("☁️ AWS Docs Assistant")
st.caption(
    "Chatbot odpowiadajacy na pytania o AWS Well-Architected Framework — "
    "wylacznie na podstawie dokumentacji, z podaniem zrodla."
)

konfiguracja = stan_konfiguracji()

with st.sidebar:
    st.subheader("Stan systemu")
    st.write("Gemini API:", "✅ gotowe" if konfiguracja["gemini"] else "❌ brak klucza")
    st.write("LangFuse:", "✅ gotowe" if konfiguracja["langfuse"] else "❌ brak klucza")
    st.divider()
    st.caption("Etap: dzien 1 — szkielet i deploy")

if not konfiguracja["gemini"]:
    st.error(
        "Brak klucza GOOGLE_API_KEY. Lokalnie: uzupelnij plik `.env`. "
        "Na Streamlit Cloud: Settings → Secrets."
    )
    st.stop()

st.success("Konfiguracja poprawna — deploy dziala.")

st.info(
    "**Co bedzie tutaj w dniu 2:** pole do zadawania pytan o dokumentacje AWS. "
    "Bot znajdzie pasujace fragmenty PDF-ow i odpowie wylacznie na ich podstawie, "
    "podajac dokument i numer strony. Gdy dokumentacja nie zawiera odpowiedzi — "
    "powie o tym wprost, zamiast zmyslac."
)

st.chat_input("Zadaj pytanie (aktywne od dnia 2)", disabled=True)
