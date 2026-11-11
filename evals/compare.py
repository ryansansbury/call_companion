"""Compare the models and pick the route: accuracy, held items, flagged email claims, cost and time per call.

    python3 evals/compare.py               into evals/model_comparison.json (the real build writes it too)

Accuracy comes from evals/scores.json. Held items, flagged claims, cost and time come from replaying each model's
recordings. Cost is what the recorded calls cost at list prices, and the monthly figure is that times 1,000, labeled
as an estimate. The route is the cheapest model whose F1 on the tuning calls clears the bar, and the best F1 on the
tuning calls when none does. The local model never takes the route, since a visitor's page shows cloud results first.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

F1_BAR = 0.85


def config():
    return json.loads(HERE.joinpath("config", "models.json").read_text(encoding="utf-8"))


def compare(views, scores, cfg=None):
    """views is {model: {call: replay.view(...)}}, scores is evals/scores.json's models section."""
    cfg = cfg or config()
    by_id = {m["id"]: m for m in cfg["models"]}
    rows = []
    for model, calls in views.items():
        done = [v for v in calls.values() if v]
        if not done:
            continue
        sc = scores.get(model, {})
        n = len(done)
        cost = sum(v["cost_usd"] for v in done) / n
        rows.append({
            "model": model, "label": by_id.get(model, {}).get("label", model),
            "vendor": by_id.get(model, {}).get("vendor"), "local": by_id.get(model, {}).get("vendor") == "Local",
            "calls": n,
            "f1": {s: (sc.get(s) or {}).get("f1") for s in ("dev", "test", "deal")},
            "held_rate": round(sum(len(v["held"]) for v in done) / max(1, sum(len(v["held"]) + len(v["kept"])
                                                                          for v in done)), 3),
            "flagged": sum(len(v.get("email_flagged") or []) for v in done),
            "cost_per_call": round(cost, 5), "per_month_estimate": round(cost * 1000, 2),
            "seconds_per_call": round(sum(v["ms"] for v in done) / n / 1000, 1),
        })
    clears = [r for r in rows if not r["local"] and (r["f1"]["dev"] or 0) >= F1_BAR]
    if clears:
        route = min(clears, key=lambda r: (r["cost_per_call"], -(r["f1"]["dev"] or 0)))["model"]
        why = "cheapest_clearing"
    else:
        cloud = [r for r in rows if not r["local"]] or rows
        route = max(cloud, key=lambda r: r["f1"]["dev"] or 0)["model"] if cloud else None
        why = "best_dev"
    return {"rows": rows, "route": route, "route_reason": why, "f1_bar": F1_BAR}


def main():
    from agents import replay
    from engine import segments
    scores = json.loads(HERE.joinpath("evals", "scores.json").read_text(encoding="utf-8"))["models"]
    views = {}
    for model in [m for m in replay.models() if m != "stand-in"]:
        views[model] = {}
        for path in sorted(HERE.joinpath("data", "transcripts").glob("*.json")):
            segs = segments.from_transcript(json.loads(path.read_text(encoding="utf-8")))
            views[model][path.stem] = replay.view(path.stem, model, segs)
    out = compare(views, scores)
    HERE.joinpath("evals", "model_comparison.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(f"Route: {out['route']} ({out['route_reason']})")


if __name__ == "__main__":
    main()
