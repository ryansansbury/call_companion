"""Score the extraction against the answer key: precision, recall and F1 by field, for every model and split.

    python3 evals/score.py                  every recorded model, into evals/scores.json
    python3 evals/score.py --dev-preview    the stand-in on the development transcripts, into
                                            evals/dev_scores.json (a pipeline check that never reaches the page)

An extracted item matches a key fact in the same field when it cites a segment where the fact was said, or uses at
least 60% of the fact's key terms, and when the fact has a number the item holds that number. Each side is judged on
its own. Precision is the share of the items the page shows (the ones the evidence check kept) that match some key
fact, and recall is the share of the key's facts and commitments that some item matches. The first version paired
items and facts one to one, which counted a fact written as two items, or two facts written as one item, twice
against the model. The tuning round showed that most of its misses were exactly that (DECISIONS.md). The items the check held are reported as the unsupported
rate. A field the call never covers is right when the model left it empty, reported as "not found." Standard library
only.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from agents import validate  # noqa: E402
from engine import numerals as numbers, segments  # noqa: E402
from engine.align import canon  # noqa: E402

FIELDS = validate.FIELDS + ["commitments"]
TERM_SHARE = 0.6


def spec(call):
    return json.loads(HERE.joinpath("calls", "specs", f"{call}.json").read_text(encoding="utf-8"))


def item_text(item):
    quotes = [e.get("quote") or "" for e in item.get("evidence") or []]
    return " ".join([item.get("value") or ""] + quotes)


def closeness(item, fact):
    """How well an item matches a fact: 0 for no match, more for a cited segment and more of the key terms."""
    if item["field"] != fact["field"]:
        return 0.0
    cited = {e.get("segment") for e in item.get("evidence") or []}
    on_segment = bool(cited & set(fact["segments"]))
    have = f" {canon(item_text(item))} "
    terms = fact.get("terms") or []
    share = sum(f" {canon(t)} " in have for t in terms) / len(terms) if terms else 0.0
    if not (on_segment or share >= TERM_SHARE):
        return 0.0
    n = fact.get("number")
    if n is not None:
        got = item.get("number")
        if not ((got is not None and isinstance(got, (int, float)) and abs(float(got) - n) < 1e-9) or
                numbers.has(item.get("value") or "", n)):
            return 0.0
    return (2.0 if on_segment else 0.0) + share


def score_call(kept, held, key):
    """Each item is right when it matches some key fact, and each fact is found when some item matches it."""
    facts = key["facts"] + key["commitments"]
    close = [[closeness(i, f) for f in facts] for i in kept]
    right = {a for a in range(len(kept)) if any(c > 0 for c in close[a])}
    found = {b for b in range(len(facts)) if any(close[a][b] > 0 for a in range(len(kept)))}
    matches = []
    for a in sorted(right):
        b = max(range(len(facts)), key=lambda j: close[a][j])
        matches.append({"item": kept[a]["id"], "fact": facts[b]["id"], "field": facts[b]["field"],
                        "closeness": round(close[a][b], 2)})
    fields = {f: {"tp": 0, "fp": 0, "found": 0, "fn": 0} for f in FIELDS}
    for a, i in enumerate(kept):
        fields.setdefault(i["field"], {"tp": 0, "fp": 0, "found": 0, "fn": 0})["tp" if a in right else "fp"] += 1
    for b, f in enumerate(facts):
        fields.setdefault(f["field"], {"tp": 0, "fp": 0, "found": 0, "fn": 0})["found" if b in found else "fn"] += 1
    absent = key.get("absent", [])
    empty = [f for f in absent if not any(i["field"] == f for i in kept)]
    return {"fields": fields, "matches": matches, "held": len(held), "kept": len(kept),
            "missed": [f["id"] for b, f in enumerate(facts) if b not in found],
            "extra": [i["id"] for a, i in enumerate(kept) if a not in right],
            "not_found": {"right": len(empty), "total": len(absent)}}


def prf(tp, fp, fn, found=None):
    """Precision from the items (tp right, fp wrong) and recall from the facts (found, fn missed)."""
    found = tp if found is None else found
    p = tp / (tp + fp) if tp + fp else None
    r = found / (found + fn) if found + fn else None
    f = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return {"precision": None if p is None else round(p, 3), "recall": None if r is None else round(r, 3),
            "f1": None if f is None else round(f, 3), "tp": tp, "fp": fp, "fn": fn, "found": found}


def roll_up(per_call):
    fields = {}
    tp = fp = fn = found = held = kept = right = total = 0
    for c in per_call.values():
        for name, v in c["fields"].items():
            agg = fields.setdefault(name, {"tp": 0, "fp": 0, "found": 0, "fn": 0})
            for k in agg:
                agg[k] += v.get(k, 0)
            tp, fp, fn, found = tp + v["tp"], fp + v["fp"], fn + v["fn"], found + v.get("found", 0)
        held += c["held"]
        kept += c["kept"]
        right += c["not_found"]["right"]
        total += c["not_found"]["total"]
    return {**prf(tp, fp, fn, found), "unsupported_rate": round(held / (held + kept), 3) if held + kept else None,
            "not_found": {"right": right, "total": total},
            "fields": {k: prf(**v) for k, v in fields.items() if v["tp"] + v["fp"] + v["found"] + v["fn"]}}


def score(model, calls, dev=False):
    per_call = {}
    for call in calls:
        rec_path = HERE.joinpath("data", "ai_runs", "extract", call, f"{model}.json")
        key_path = HERE.joinpath("data", "dev_key" if dev else "key", f"{call}.json")
        if not rec_path.exists() or not key_path.exists():
            continue
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        tpath = HERE.joinpath("data", "dev_transcripts" if dev else "transcripts", f"{call}.json")
        segs = segments.from_transcript(json.loads(tpath.read_text(encoding="utf-8")))
        kept, held, _ = validate.extract(rec["reply"], segs)
        per_call[call] = score_call(kept, held, json.loads(key_path.read_text(encoding="utf-8")))
    if not per_call:
        return None
    return {**roll_up(per_call), "calls": per_call}


def models_recorded():
    root = HERE.joinpath("data", "ai_runs", "extract")
    return sorted({p.stem for p in root.glob("*/*.json")})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dev-preview", action="store_true")
    a = ap.parse_args(argv)
    specs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(HERE.glob("calls/specs/*.json"))]
    splits = {s: [x["id"] for x in specs if x["split"] == s] for s in ("dev", "test", "deal")}
    models = ["stand-in"] if a.dev_preview else [m for m in models_recorded() if m != "stand-in"]
    if not a.dev_preview:
        from evals import freeze
        if not freeze.ready("key") or not freeze.ready("aligned"):
            raise SystemExit("The key and the aligned key have to be frozen and unchanged before scoring.")
    out = {"source": "dev-preview" if a.dev_preview else "transcripts", "models": {}}
    for m in models:
        out["models"][m] = {s: score(m, calls, a.dev_preview) for s, calls in splits.items()}
        for s, v in out["models"][m].items():
            if v:
                print(f"  {m} {s}: F1 {v['f1']}, precision {v['precision']}, recall {v['recall']}, "
                      f"held {v['unsupported_rate']}, not found {v['not_found']['right']}/{v['not_found']['total']}")
    name = "dev_scores.json" if a.dev_preview else "scores.json"
    HERE.joinpath("evals", name).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote evals/{name}")


if __name__ == "__main__":
    main()
