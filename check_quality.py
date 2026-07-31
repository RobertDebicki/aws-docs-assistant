"""Ręczny sprawdzian jakości odpowiedzi.

    python check_quality.py

Nie jest to test automatyczny — nie ma tu asercji, bo odpowiedzi modelu nie są
deterministyczne co do słowa. To narzędzie do OGLĄDANIA wyników: czy bot trafia
w sedno, czy cytuje sensowne źródła i — najważniejsze — czy potrafi przyznać,
że czegoś nie wie.

Ostatnie pytanie jest CELOWO spoza dokumentacji. To najważniejszy przypadek
testowy w całym RAG: system, który na takie pytanie zmyśla odpowiedź, jest
gorszy niż brak systemu, bo brzmi wiarygodnie i myli użytkownika.
"""

import rag

QUESTIONS = [
    ("Co dokumentacja mówi o szyfrowaniu danych w spoczynku?", "w zakresie"),
    ("Jak kontrolować koszty w architekturze AWS?", "w zakresie"),
    ("Jakie są zasady zarządzania tożsamością i dostępem?", "w zakresie"),
    ("Jaka jest stolica Australii?", "POZA zakresem — bot ma odmówić"),
]


def main() -> None:
    index = rag.load_index()

    for question, kind in QUESTIONS:
        print("=" * 70)
        print(f"PYTANIE ({kind}): {question}")
        print("-" * 70)

        answer = rag.ask(index, question)
        print(answer.text)

        if answer.sources:
            print(f"\nŹródła ({len(answer.sources)}):")
            for s in answer.sources:
                print(f"  - {s.document}, strona {s.page}")
        print()


if __name__ == "__main__":
    main()
