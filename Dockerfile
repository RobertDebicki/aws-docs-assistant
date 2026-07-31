# Obraz pod Hugging Face Spaces.
# HF wymaga dwoch rzeczy: aplikacja slucha na porcie 7860 i nie dziala jako root.

FROM python:3.11-slim

# HF Spaces uruchamia kontener jako user o UID 1000 — bez tego brak uprawnien do zapisu.
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /home/user/app

# requirements kopiujemy osobno i PRZED reszta kodu — dzieki temu Docker
# cache'uje warstwe z zaleznosciami i kolejne deploye trwaja sekundy zamiast minut.
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY --chown=user . .

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
