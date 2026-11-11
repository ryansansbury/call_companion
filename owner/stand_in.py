"""A stand-in for a model, for dry runs with no network: it answers each step from the answer key.

It exists to prove the pipeline end to end (inputs, validation, records, scoring and the page) before I spend
anything. Its replies are labeled "Stand-in (no model)" everywhere, and the build never shows them as AI results on
the public page. A1 quotes whole segments (the one holding the fact's key terms and number, or two when the call
spreads them), A2 writes plain sentences from the checked facts, and A3 cites the rep's first and last turns.
"""
import json
import re
from pathlib import Path

from engine import claims, evidence, numerals as numbers

HERE = Path(__file__).resolve().parent.parent


class Backend:
    def __init__(self, call, segs):
        self.call = call
        self.segs = segs
        self.spec = json.loads(HERE.joinpath("calls", "specs", f"{call}.json").read_text(encoding="utf-8"))

    def __call__(self, system, user):
        payload = json.loads(user.split("\n\nYour reply had these problems")[0])
        if "segments" in payload and "coaching" in payload:
            text = self.coach(payload)
        elif "segments" in payload:
            text = self.extract()
        else:
            text = self.followup(payload)
        return text, {"model": "stand-in", "input_tokens": len(user) // 4, "output_tokens": len(text) // 4,
                      "cost_usd": 0.0}

    def described(self):
        return {"backend": "stand-in", "model": "stand-in"}

    def _segments_for(self, terms, number=None, value=""):
        """The segment holding every term and the number, or else the one with the most terms plus the nearest one
        that holds the number. Empty when no segment has a term. When several segments hold every term, the one that
        shares the most words with the fact's value wins, so "counsel has it the day it comes in" beats an earlier
        line that only mentions counsel."""
        def hits(g):
            low = evidence.norm(g["text"])
            return sum(1 for t in terms if evidence.norm(t) in low)
        def has_number(g):
            return number is None or numbers.has(g["text"], number)
        filler = {"the", "and", "for", "but", "you", "our", "its", "has", "are", "was", "with", "that", "this", "they",
                  "them", "then", "than", "from", "into", "about", "your", "who", "can", "all"}
        words = {w for w in re.findall(r"[a-z]+", value.lower()) if len(w) > 2 and w not in filler}
        def overlap(g):
            return len(words & set(re.findall(r"[a-z]+", g["text"].lower())))
        if not terms:
            return []
        full = [g for g in self.segs if hits(g) == len(terms) and has_number(g)]
        if full:
            return [max(full, key=lambda g: (overlap(g), -self.segs.index(g)))]
        best = max(self.segs, key=hits, default=None)
        if best is None or hits(best) == 0:
            return []
        if has_number(best):
            return [best]
        at = self.segs.index(best)
        near = sorted((g for g in self.segs if numbers.has(g["text"], number)),
                      key=lambda g: abs(self.segs.index(g) - at))
        return [best] + near[:1]

    @staticmethod
    def _due(found, value=""):
        """The date phrase in the quoted text that the fact is about, as spoken. A quote can hold two dates ("by
        Thursday, and Linda, you'd let us know by Wednesday the thirtieth"), so the phrase sharing a word with the
        fact's value wins, and the first phrase is the fallback."""
        spans = [m.group(0) for g in found for m in claims.DATE_SPAN.finditer(g["text"])]
        words = set(re.findall(r"[a-z]+", value.lower())) - {"by", "on", "the", "next", "this", "of", "until"}
        for s in spans:
            if set(re.findall(r"[a-z]+", s.lower())) & words:
                return s
        return spans[0] if spans else None

    def _proper(self, word):
        """True when the call says this word with a capital somewhere other than the start of a sentence."""
        for g in self.segs:
            for s in claims.sentences(g["text"]):
                if word in re.findall(r"[A-Za-z']+", s)[1:]:
                    return True
        return False

    def _lead(self, value, names=()):
        """The value as the middle of a sentence: its first letter lowered unless the first word is a name, either one
        the email's people carry or one the call says with a capital."""
        first = re.findall(r"[A-Za-z']+", value)[:1]
        if first and (first[0] in {n.split()[0] for n in names if n} or self._proper(first[0])):
            return value
        return value[0].lower() + value[1:]

    def extract(self):
        fields = {}
        for f in self.spec["facts"]:
            found = self._segments_for(f.get("terms", []), f.get("number"), f["value"])
            if not found:
                continue
            item = {"value": f["value"], "evidence": [{"segment": g["id"], "quote": g["text"]} for g in found]}
            for k in ("number", "unit", "owner"):
                if f.get(k) is not None:
                    item[k] = f[k]
            due = self._due(found, f["value"]) if f["field"] in ("next_steps", "close_date") else None
            if due:
                item["due"] = due
            fields.setdefault(f["field"], []).append(item)
        commitments = []
        for k in self.spec.get("commitments", []):
            found = self._segments_for(k.get("terms", []), None, k["what"])
            if found:
                c = {"by": k["by"], "who": k["who"], "what": k["what"], "kind": k["kind"],
                     "evidence": [{"segment": g["id"], "quote": g["text"]} for g in found]}
                due = self._due(found, k["what"])
                if due:
                    c["due"] = due
                commitments.append(c)
        return json.dumps({"fields": fields, "commitments": commitments})

    def followup(self, payload):
        facts = payload["facts"]
        pick = [f for f in facts if f["field"] in ("metrics", "pain")][:2]
        steps = [f for f in facts if f["field"] == "next_steps"][:3]
        conc = [f for f in facts if f.get("field") == "commitments" and "waive" in f["value"].lower()]
        sents = [{"text": f"Thanks for the time today, {payload['to'][0].split()[0]}.", "facts": []}]
        names = [payload.get("rep", "")] + list(payload.get("to", []))
        for f in pick:
            sents.append({"text": f"You mentioned {self._lead(f['value'], names)}.", "facts": [f["id"]]})
        for f in conc:
            sents.append({"text": "As discussed, we'll waive the installation.", "facts": [f["id"]]})
        for f in steps:
            sents.append({"text": f"Next, {self._lead(f['value'], names)}.", "facts": [f["id"]]})
        sents.append({"text": f"Talk soon, {payload['rep'].split()[0]}", "facts": []})
        return json.dumps({"subject": "Following up on today's call", "sentences": sents})

    def coach(self, payload):
        mine = [g for g in payload["segments"] if g["speaker"] == payload["rep"]]
        def point(g, text):
            return {"text": text, "segment": g["id"], "quote": " ".join(g["text"].split()[:6])}
        strengths = [point(g, "Asked a clear question that kept the buyer talking.") for g in mine[:3]]
        improvements = [point(g, "Could have asked a follow-up question here.") for g in mine[-3:]]
        return json.dumps({"strengths": strengths, "improvements": improvements})
