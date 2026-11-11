"""Check that every fact the AI hands back is really in the call, before the page shows it.

An item passes when each of its quotes appears in the segment it cites (after evening out case, punctuation and
spacing), and every number in its value is in one of those quotes, in words or digits. Dates are left out of the
number check, since a value may name a weekday or a month that the speaker said differently. An item that fails is
held with its reasons, counted as unsupported, and never shown as a fact. Standard library only, and the same rules
run in the build and in the owner's recorder.
"""
import re

from engine import numerals as numbers

MONTHS = r"(?:january|february|march|april|may|june|july|august|september|october|november|december)"
DATEISH = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b" + MONTHS + r"\s+\d{1,2}(?:st|nd|rd|th)?\b|\b\d{1,2}(?:st|nd|rd|th)\b",
                     re.I)


def norm(text):
    """Lowercase words and digits only, with "14,000" as "14000" and hyphens as spaces."""
    t = (text or "").lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    t = re.sub(r"(\d),(\d)", r"\1\2", t).replace("-", " ")
    t = re.sub(r"[^a-z0-9$%' ]+", " ", t)
    return " ".join(t.split())


def quote_in(quote, text):
    q = norm(quote)
    return bool(q) and f" {q} " in f" {norm(text)} "


def value_numbers(item):
    """Numbers an item claims: its number field and any number written in digits in its value, outside a date.
    Number words are left out ("year one," "no one," "two other vendors"), since the prompt has the model write the
    numbers it claims as digits."""
    found = []
    if item.get("number") is not None:
        found.append(item["number"])
    found += [v for v, _, _ in numbers.written(DATEISH.sub(" ", item.get("value") or ""))]
    return found


def check(item, segments_by_id):
    """[] when the item is supported, or the reasons it isn't."""
    problems = []
    evidence = item.get("evidence") or []
    if not evidence:
        return ["no evidence"]
    quotes = []
    for e in evidence:
        seg = segments_by_id.get(e.get("segment"))
        if seg is None:
            problems.append(f"cites {e.get('segment')}, which isn't a segment of this call")
            continue
        if not quote_in(e.get("quote"), seg["text"]):
            problems.append(f"the quote isn't in {seg['id']}")
            continue
        quotes.append(e["quote"])
    heard = " ".join(quotes)
    for value in value_numbers(item):
        if quotes and not numbers.has(heard, value):
            problems.append(f"{value:g} isn't in the quote" if isinstance(value, (int, float)) else
                            f"{value} isn't in the quote")
    return problems
