"""The answer key in the shapes the checks read.

facts() turns a call spec's facts and commitments into checked facts that quote the script lines they sit on, and
table() builds the claim checker's table from them the way the build builds one from a model's checked facts. The
planted claims, the clean emails and the engine tests all judge against this key and never against a model's
output, so the claim checker is measured on its own.
"""
import json
from pathlib import Path

from agents import inputs
from engine import claims
from generate import scripts
from generate.validate import heard

HERE = Path(__file__).resolve().parent.parent


def spec(call):
    return json.loads(HERE.joinpath("calls", "specs", f"{call}.json").read_text(encoding="utf-8"))


def lines(call):
    """Each script line as a listener hears it, cut lines stopping where the next speaker cuts in."""
    out = {}
    for t in scripts.load(HERE.joinpath("calls", "scripts", f"{call}.md")):
        out[t["id"]] = " ".join(heard(t)) if t["marks"].get("cut") else t["text"]
    return out


def facts(call):
    """The key's facts and commitments as checked facts, quoting the script lines they sit on."""
    s, said = spec(call), lines(call)
    out = []
    for f in s["facts"]:
        out.append({"id": f["id"], "field": f["field"], "value": f["value"], "number": f.get("number"),
                    "unit": f.get("unit"), "date": f.get("date"),
                    "quotes": [said[x] for x in (f.get("lines") or [f["line"]])]})
    for k in s.get("commitments", []):
        out.append({"id": k["id"], "field": "commitments", "kind": k["kind"], "value": k["what"],
                    "date": k.get("due"), "approved": k.get("approved", True), "policy": k.get("policy"),
                    "quotes": [said[k["line"]]]})
    return out


def table(call, approved=()):
    """The claim checker's table for a call, built from the key."""
    s = spec(call)
    tbl = claims.table(facts(call), s["date"], inputs.roster(s), inputs.companies(s),
                       "\n".join(lines(call).values()))
    return claims.approve(tbl, approved) if approved else tbl
