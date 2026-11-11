"""Numbers the way people say them and the way a transcript writes them.

A call says "fourteen thousand," "forty-five hundred" or "twelve hundred and sixty," and a transcript writes
"$14,000," "4,500" or "1260." Both sides of every check come through here, so a quote and a value agree on what
number they hold. Standard library only.
"""
import re

SMALL = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
         "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
         "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
         "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
SCALES = {"thousand": 1000, "million": 1000000}
DIGITS = re.compile(r"\$?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:\s*(k|thousand|million)\b)?\s*(%|percent)?", re.I)
SCALE_AFTER_DIGITS = re.compile(r"\d\s*$")
TOKEN = re.compile(r"[a-z]+|\d[\d,.]*%?", re.I)


def _words_value(tokens):
    total, current = 0, 0
    for t in tokens:
        if t == "and":
            continue
        if t in SMALL:
            current += SMALL[t]
        elif t == "hundred":
            current = (current or 1) * 100
        elif t in SCALES:
            total += (current or 1) * SCALES[t]
            current = 0
    return total + current


def spoken(text):
    """Every number written out in words, as (value, start, end) over the lowercased text."""
    low = text.lower().replace("-", " ")
    out, run, start, end = [], [], None, None
    for m in re.finditer(r"[a-z]+", low):
        w = m.group(0)
        is_num = w in SMALL or w == "hundred" or w in SCALES
        joins = w == "and" and run and run[-1] in ("hundred", "thousand", "million")
        lead = w == "a" and not run
        if is_num or joins:
            if not run:
                start = m.start()
            run.append(w)
            end = m.end()
            continue
        if lead:
            nxt = low[m.end():].lstrip()
            if nxt.startswith(("hundred", "thousand")):
                start, run, end = m.start(), ["one"], m.end()
                continue
        if run:
            _flush(run, start, end, low, out)
            run = []
    if run:
        _flush(run, start, end, low, out)
    return out


def _flush(run, start, end, low, out):
    """Keep a run of number words, unless it's only a scale word after digits ("20 thousand" is one number, read
    by written())."""
    while run and run[-1] == "and":
        run.pop()
    if not any(t != "and" for t in run):
        return
    if all(t in SCALES or t == "hundred" for t in run) and SCALE_AFTER_DIGITS.search(low[:start]):
        return
    out.append((_words_value(run), start, end))


def written(text):
    """Every number written in digits, as (value, start, end), with "k" or "thousand" after it read as thousands."""
    out = []
    for m in DIGITS.finditer(text):
        raw = m.group(1).replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        scale = (m.group(2) or "").lower()
        value *= 1000 if scale in ("k", "thousand") else 1000000 if scale == "million" else 1
        out.append((int(value) if value == int(value) else value, m.start(), m.end()))
    return out


def numbers(text):
    """Every number in the text, spoken or written, in order of appearance."""
    found = [(v, s, e) for v, s, e in spoken(text)] + [(v, s, e) for v, s, e in written(text)]
    return [v for v, _, _ in sorted(found, key=lambda x: x[1])]


def has(text, value):
    """Whether the text holds this number, in words or in digits."""
    target = float(value)
    return any(abs(float(v) - target) < 1e-9 for v in numbers(text))
