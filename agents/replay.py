"""Replay a model's recorded runs for one call, validating every reply again exactly as the recorder did.

The build never calls a model. It reads data/ai_runs/<step>/<call>/<model>.json, checks each reply again with
agents/validate.py and hands the page only what passes. A record made with a prompt that no longer matches the
current prompt file is refused, so an old run can't stand in for the prompts the page describes.
"""
import json
from pathlib import Path

from agents import inputs, validate
from engine import claims

HERE = Path(__file__).resolve().parent.parent
RUNS = HERE.joinpath("data", "ai_runs")
STEPS = ("extract", "followup", "followup-approved", "coach")


class Stale(Exception):
    pass


def load(step, call, model, strict=True):
    path = RUNS.joinpath(step, call, f"{model}.json")
    if not path.exists():
        return None
    rec = json.loads(path.read_text(encoding="utf-8"))
    if strict and rec.get("prompt_hash") != inputs.prompt_hash(step.split("-")[0]):
        raise Stale(f"{step} {call} {model} was recorded with an older prompt. Record it again.")
    return rec


def models():
    """Every model with at least one extraction recorded."""
    return sorted({p.stem for p in RUNS.joinpath("extract").glob("*/*.json")})


def view(call, model, segs, strict=True):
    """Everything the page shows for one call and one model, validated again. None when nothing was recorded."""
    s = inputs.spec(call)
    ext = load("extract", call, model, strict)
    if not ext:
        return None
    kept, held, problems = validate.extract(ext["reply"], segs)
    facts = validate.checker_facts(kept, segs, s["date"])
    tbl = validate.checker_table(facts, segs, s)
    out = {"kept": kept, "held": held, "problems": problems, "facts": facts, "table": tbl,
           "cost_usd": 0.0, "ms": 0, "tokens_in": 0, "tokens_out": 0, "dates": {}, "labels": {}}
    recs = {"extract": ext}
    for step in STEPS[1:]:
        recs[step] = load(step, call, model, strict)
    for step, rec in recs.items():
        if not rec:
            continue
        meta = rec.get("meta") or {}
        out["cost_usd"] += meta.get("cost_usd") or 0.0
        out["tokens_in"] += meta.get("input_tokens") or 0
        out["tokens_out"] += meta.get("output_tokens") or 0
        out["ms"] += rec.get("ms") or 0
        out["dates"][step] = rec.get("date")
        out["labels"][step] = rec.get("label")
    concessions = [f["id"] for f in facts if f.get("kind") == "concession"]
    out["concessions"] = concessions
    for step, approved, key in (("followup", (), "email"), ("followup-approved", tuple(concessions), "email_approved")):
        rec = recs.get(step)
        if rec:
            draft, flagged, probs = validate.followup(rec["reply"], tbl, approved)
            out[key] = draft
            out[key + "_flagged"] = flagged
            out[key + "_problems"] = probs
        else:
            out[key] = None
    if recs.get("coach"):
        note, note_held, probs = validate.coach(recs["coach"]["reply"], segs)
        out["coach"] = note if note and not probs else None
        out["coach_held"] = note_held
    else:
        out["coach"] = None
    out["approved_table"] = claims.approve(tbl, concessions) if concessions else None
    return out
