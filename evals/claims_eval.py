"""Score the claim checker on the planted bad claims and the clean emails, against the answer key.

    python3 evals/claims_eval.py            print the results and write evals/claim_results.json

A planted claim is caught when the checker flags a claim that overlaps its bad words, and it's the right call when
the status matches as well (a floated concession needs approval, and everything else is unsupported). A clean email
is a false alarm when the checker flags anything in it. The bars are 95% caught and at most one false alarm in ten
clean emails. Standard library only.
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import claims  # noqa: E402
from evals import key  # noqa: E402

_TABLES = {}


def tbl(call, approved=()):
    k = (call, tuple(approved))
    if k not in _TABLES:
        _TABLES[k] = key.table(call, approved)
    return _TABLES[k]


def planted():
    rows = []
    for p in json.loads(HERE.joinpath("evals", "planted_claims.json").read_text(encoding="utf-8"))["claims"]:
        result = claims.check_email(p["sentence"], tbl(p["call"]))
        found = [c for s in result for c in s["claims"]]
        a = p["sentence"].index(p["bad"])
        b = a + len(p["bad"])
        hits = [c for c in found if c["status"] != "supported" and c["start"] < b and a < c["end"]]
        extra = [c for c in found if c["status"] != "supported" and c not in hits]
        rows.append({"id": p["id"], "call": p["call"], "type": p["type"], "how": p["how"], "sentence": p["sentence"],
                     "bad": p["bad"], "caught": bool(hits), "right": any(c["status"] == p["expect"] for c in hits),
                     "reason": hits[0]["reason"] if hits else None, "check": hits[0].get("check") if hits else None,
                     "extra": [{"text": c["text"], "reason": c["reason"]} for c in extra]})
    return rows


def clean():
    rows = []
    for e in json.loads(HERE.joinpath("evals", "clean_emails.json").read_text(encoding="utf-8"))["emails"]:
        result = claims.check_email(e["text"], tbl(e["call"], e["approved"]))
        found = [c for s in result for c in s["claims"]]
        bad = [{"text": c["text"], "reason": c["reason"]} for c in found if c["status"] != "supported"]
        rows.append({"id": e["id"], "call": e["call"], "claims": len(found), "flagged": bad})
    return rows


def main():
    p, c = planted(), clean()
    caught = sum(r["caught"] for r in p)
    right = sum(r["right"] for r in p)
    alarms = sum(1 for r in c if r["flagged"])
    by_type = {}
    for r in p:
        t = by_type.setdefault(r["type"], {"planted": 0, "caught": 0})
        t["planted"] += 1
        t["caught"] += r["caught"]
    out = {"planted": len(p), "caught": caught, "right_status": right, "catch_rate": round(caught / len(p), 3),
           "by_type": by_type, "clean_emails": len(c), "clean_claims": sum(r["claims"] for r in c),
           "false_alarm_emails": alarms, "false_alarm_rate": round(alarms / len(c), 3),
           "bars": {"catch_rate": 0.95, "false_alarm_rate": 0.1},
           "passes": caught / len(p) >= 0.95 and alarms / len(c) <= 0.1,
           "checks": dict(Counter(r["check"] for r in p if r["caught"])), "rows": p, "clean": c}
    HERE.joinpath("evals", "claim_results.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n",
                                                           encoding="utf-8")
    print(f"Planted: {caught}/{len(p)} caught ({out['catch_rate']:.0%}), {right} with the right status")
    for t, v in by_type.items():
        print(f"  {t:8} {v['caught']}/{v['planted']}")
    for r in p:
        if not r["caught"]:
            print(f"  MISSED {r['id']} {r['call']} {r['type']}/{r['how']}: {r['sentence']}")
        elif not r["right"]:
            print(f"  WRONG STATUS {r['id']}: {r['reason']}")
        for x in r["extra"]:
            print(f"  EXTRA {r['id']}: {x['text']!r} {x['reason']}")
    print(f"Clean: {alarms}/{len(c)} emails with a false alarm, {out['clean_claims']} claims checked")
    for r in c:
        for x in r["flagged"]:
            print(f"  FALSE ALARM {r['id']} {r['call']}: {x['text']!r} {x['reason']}")
    print("Passes both bars." if out["passes"] else "Misses a bar.")


if __name__ == "__main__":
    main()
