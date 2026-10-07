"""
Generate simulated survey responses to test a survey analysis before real data arrives.

The output is a CSV laid out like a Google Forms response export, so the same
spreadsheet formulas, charts or scripts can be pointed at it. Every row is
marked as simulated so it can't be confused with real answers.

Edit QUESTIONS below to match your form, then run:
    python simulate_responses.py            # 250 rows -> simulated_responses.csv
    python simulate_responses.py 500 out.csv
"""

import csv
import random
import sys
from collections import Counter

# Question text -> {answer option: share of responses}.
# Shares don't need to add up to 1; they are normalised.
QUESTIONS = {
    "What grade are you in?": {"9": 0.25, "10": 0.30, "11": 0.25, "12": 0.20},
    "How many hours do you sleep on school nights?": {
        "Less than 6": 0.15,
        "6-7": 0.40,
        "7-8": 0.30,
        "More than 8": 0.15,
    },
    "Do you eat breakfast?": {"Yes": 0.6, "No": 0.4},
}


def exact_counts(ratios, n):
    """Split n into whole counts that match the ratios as closely as possible."""
    total = sum(ratios.values())
    raw = {opt: n * share / total for opt, share in ratios.items()}
    counts = {opt: int(v) for opt, v in raw.items()}
    # Hand out the leftover rows to the options with the largest remainders.
    leftover = n - sum(counts.values())
    for opt in sorted(raw, key=lambda o: raw[o] - counts[o], reverse=True)[:leftover]:
        counts[opt] += 1
    return counts


def simulate(n):
    columns = {}
    for question, ratios in QUESTIONS.items():
        answers = [opt for opt, c in exact_counts(ratios, n).items() for _ in range(c)]
        random.shuffle(answers)
        columns[question] = answers
    return [
        {"Response": f"SIMULATED-{i + 1}", **{q: columns[q][i] for q in QUESTIONS}}
        for i in range(n)
    ]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 250
    path = sys.argv[2] if len(sys.argv) > 2 else "simulated_responses.csv"

    rows = simulate(n)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Response", *QUESTIONS])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {n} simulated responses to {path}\n")
    for question in QUESTIONS:
        print(question)
        for opt, c in Counter(r[question] for r in rows).most_common():
            print(f"  {opt:<15} {c:>4}  ({c / n:.1%})")
        print()


if __name__ == "__main__":
    main()
