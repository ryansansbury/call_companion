"""What each AI step sees: the user message, built the same way in the recorder and in the build's replay check.

A recording counts only if the model saw exactly what code would send today, so these builders are deterministic and
their output is hashed into every recording.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def spec(call):
    return json.loads(HERE.joinpath("calls", "specs", f"{call}.json").read_text(encoding="utf-8"))


def people(s):
    cast = json.loads(HERE.joinpath("calls", "cast.json").read_text(encoding="utf-8"))
    roster = cast["deal"] if s["kind"] == "deal" else s["cast"]
    return [{"code": c, "name": roster[c]["name"], "role": roster[c]["role"], "company": roster[c]["company"],
             "side": roster[c]["side"]} for c in s["speakers"]]


def roster(s):
    """Everyone a call can name: the whole deal cast on a deal call (the CFO comes up before she joins), or a scored
    call's own two people."""
    cast = json.loads(HERE.joinpath("calls", "cast.json").read_text(encoding="utf-8"))
    people = cast["deal"] if s["kind"] == "deal" else s["cast"]
    return [{"name": p["name"], "role": p["role"]} for p in people.values()]


def companies(s):
    cast = json.loads(HERE.joinpath("calls", "cast.json").read_text(encoding="utf-8"))
    return [cast["seller"]] + ([cast["buyer"]] if s["kind"] == "deal" else [])


def extract_input(call, segs):
    s = spec(call)
    return {"call": call, "date": s["date"], "seller": "Brinewatch", "people": people(s),
            "segments": [{"id": g["id"], "speaker": g["speaker"], "start": g["start"], "text": g["text"]}
                         for g in segs]}


def followup_input(call, facts, approved=()):
    """The checked facts and the commitments the rep may repeat. Unapproved concessions stay out."""
    s = spec(call)
    ppl = people(s)
    rep = next(p for p in ppl if p["side"] == "seller")
    to = [p["name"] for p in ppl if p["side"] == "buyer"]
    usable = []
    for f in facts:
        if f["field"] == "commitments" and f.get("kind") == "concession" and f["id"] not in approved:
            continue
        item = {"id": f["id"], "field": f["field"], "value": f["value"]}
        for k in ("number", "unit", "due", "owner"):
            if f.get(k) is not None:
                item[k] = f[k]
        usable.append(item)
    return {"call": call, "date": s["date"], "rep": rep["name"], "company": "Brinewatch", "to": to, "facts": usable}


def coach_input(call, segs, metrics, rep_code):
    s = spec(call)
    return {"call": call, "date": s["date"], "rep": rep_code,
            "segments": [{"id": g["id"], "speaker": g["speaker"], "start": g["start"], "text": g["text"]}
                         for g in segs],
            "coaching": metrics}


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def prompt(step):
    name = {"extract": "extract.md", "followup": "followup.md", "coach": "coach.md"}[step]
    return HERE.joinpath("prompts", name).read_text(encoding="utf-8")


def prompt_hash(step):
    return hashlib.sha256(prompt(step).encode()).hexdigest()[:16]
