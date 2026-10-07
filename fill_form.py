#!/usr/bin/env python3
"""Submit a Google Form N times with a fixed answer ratio (your own form, test data).

Usage:
    python3 fill_form.py --dry-run          # show planned counts, send nothing
    python3 fill_form.py                    # send 250 submissions
    python3 fill_form.py -n 250 --min-delay 1 --max-delay 3

Entry IDs are read from the live form, so only the question titles / option
labels below have to match the form. Standard library only.
"""
import argparse
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

FORM_URL = ("https://docs.google.com/forms/d/e/"
            "1FAIpQLScecCR4y_uVnkCvB5rarOqrzq8sUTNx14pAkhX0yyhRWZ549g")

# Ratios taken from the Responses tab (98 responses).
# "single" = multiple choice (weights sum to the whole group)
# "multi"  = checkboxes (each option is picked by that share of respondents, independently)
# Keys are matched as case-insensitive prefixes of the question title / option label.
PLAN = {
    "Mis on Teie sugu?": ("single", {
        "Mees": 23.5, "Naine": 73.5, "Muu": 3.1}),
    "Mida ootaksite kõige rohkem meie tootest?": ("multi", {
        "Lennuk lendab": 80.6,
        "Lennuk püsib koos": 60.2,
        "Taaskasutatud puitu": 25.5,
        "Mõistekaardid": 32.7,
        "Pakend oleks ilus": 13.3}),
    "Mis on Teie vanus?": ("single", {
        "10-20": 12.2, "21-30": 12.2, "31-40": 11.2,
        "41-50": 32.7, "51-60": 23.5, "61+": 8.2}),
    "Kui tihti mänguasju ostate?": ("single", {
        "Harva": 53.1, "Ainult tähtpäevadeks": 31.6, "Tihti": 15.3}),
    "Millist lisaväärtust soovite meie tootega?": ("multi", {
        "Värvipliiatsid": 26.6,
        "Kleepsud": 59.6,
        "Inspereerivad": 31.9}),
    "Mis hinna eest ostaksite meie Plennukit?": ("single", {
        "15€": 32.7, "20€": 51.0, "25€": 10.2, "30€": 6.1}),
}


def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def find_key(text, keys):
    t = norm(text)
    for k in keys:
        if t.startswith(norm(k)) or norm(k).startswith(t) and t:
            return k
    return None


def allocate(weights, n):
    """Largest-remainder rounding so counts add up to exactly n."""
    total = sum(weights.values())
    raw = {k: v / total * n for k, v in weights.items()}
    counts = {k: int(x) for k, x in raw.items()}
    left = n - sum(counts.values())
    for k in sorted(raw, key=lambda k: raw[k] - counts[k], reverse=True)[:left]:
        counts[k] += 1
    return counts


def single_column(weights, n):
    col = [k for k, c in allocate(weights, n).items() for _ in range(c)]
    random.shuffle(col)
    return col


def multi_column(weights, n):
    """Each option is ticked by exactly round(p*n) respondents; >=1 option per respondent."""
    ticks = []
    for opt, pct in weights.items():
        flags = [True] * round(pct / 100 * n) + [False] * (n - round(pct / 100 * n))
        random.shuffle(flags)
        ticks.append((opt, flags))
    rows = [[o for o, f in ticks if f[i]] for i in range(n)]
    for r in rows:  # nobody submits an empty required checkbox
        if not r:
            r.append(max(weights, key=weights.get))
    return rows


def fetch(url, data=None):
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"})
    return urllib.request.urlopen(req, timeout=30)


def load_form():
    html = fetch(FORM_URL + "/viewform").read().decode("utf-8")
    m = re.search(r"FB_PUBLIC_LOAD_DATA_\s*=\s*(.*?);\s*</script>", html, re.S)
    if not m:
        sys.exit("Could not read the form (does it require Google sign-in?).")
    data = json.loads(m.group(1))
    items = data[1][1]
    sections = sum(1 for it in items if it[3] == 8)
    questions = []
    for it in items:
        if it[3] in (2, 4) and it[4]:  # 2 = multiple choice, 4 = checkboxes
            questions.append({"title": it[1], "entry": it[4][0][0],
                              "options": [o[0] for o in it[4][0][1]]})
    return questions, sections


def build_submissions(questions, n):
    columns = []  # (entry_id, [value or [values] per submission])
    for q in questions:
        key = find_key(q["title"], PLAN)
        if key is None:
            print(f"! no ratio for question '{q['title']}' -> left unanswered")
            continue
        kind, weights = PLAN[key]
        resolved = {}
        for label, w in weights.items():
            real = next((o for o in q["options"] if norm(o).startswith(norm(label))), None)
            if real is None:
                sys.exit(f"Option '{label}' not found in question '{q['title']}'. "
                         f"Form has: {q['options']}")
            resolved[real] = w
        col = single_column(resolved, n) if kind == "single" else multi_column(resolved, n)
        columns.append((q["entry"], q["title"], col))
    return columns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=250)
    ap.add_argument("--min-delay", type=float, default=1.0)
    ap.add_argument("--max-delay", type=float, default=3.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    questions, sections = load_form()
    columns = build_submissions(questions, args.n)

    for _, title, col in columns:
        flat = [v for row in col for v in (row if isinstance(row, list) else [row])]
        print(f"\n{title}")
        for v in sorted(set(flat)):
            print(f"   {v:<45} {flat.count(v):>4}  ({flat.count(v) / args.n:.1%})")
    if args.dry_run:
        return

    page_history = ",".join(str(i) for i in range(sections + 1))
    ok = 0
    for i in range(args.n):
        fields = [("fvv", "1"), ("pageHistory", page_history)]
        for entry, _, col in columns:
            vals = col[i] if isinstance(col[i], list) else [col[i]]
            fields += [(f"entry.{entry}", v) for v in vals]
        body = urllib.parse.urlencode(fields).encode()
        for attempt in range(3):
            try:
                if fetch(FORM_URL + "/formResponse", body).status == 200:
                    ok += 1
                    break
            except urllib.error.URLError as e:
                print(f"  #{i + 1} attempt {attempt + 1} failed: {e}")
                time.sleep(2 ** attempt)
        else:
            print(f"  #{i + 1} gave up")
        print(f"\rsent {ok}/{args.n}", end="", flush=True)
        time.sleep(random.uniform(args.min_delay, args.max_delay))
    print(f"\nDone: {ok}/{args.n} submitted.")


if __name__ == "__main__":
    main()
