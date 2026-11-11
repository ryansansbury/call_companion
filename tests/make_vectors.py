"""Write tests/vectors/claims.json: the cases the Python and JavaScript claim checkers must agree on.

    python3 tests/make_vectors.py

The cases are the planted claims, the clean emails, the engine tests' sentences and a set of date phrases, each with
what engine/claims.py returns for it. tests/js/check_claims.js runs site/claims.js on the same cases and tables.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import claims, dates  # noqa: E402
from evals import key  # noqa: E402

EXTRA = [
    ("deal-3", (), "Thanks for your time today Linda. Year one comes to about $50,000, and we'll start with a "
                   "four-truck pilot for thirty days with a clean opt-out."),
    ("deal-3", (), "Hardware comes to $29,000 for the fleet. Installs start October 5."),
    ("deal-3", (), "We'll waive the installation fee to keep you on schedule. We can also take 20% off the software."),
    ("deal-3", ("d3k02",), "We'll waive the installation."),
    ("deal-3", (), "Feel free to forward this to Linda. Linda Marsh, your CFO, makes the decision."),
    ("deal-3", (), "Losing a load like that hurts. Hardware is about $31,000."),
    ("deal-2", (), "Priya will send a written pilot plan for the four trucks by Thursday, and Tom will send the "
                   "security questionnaire by Friday."),
    ("deal-1", (), "I'll send the invite for next Tuesday at ten. That one load cost you about $5,000 in seafood."),
    ("s01", (), "Angela will take it to Susan Park herself. Kevin's team can help."),
    ("s03", (), "The walk-in died on a Saturday night and nobody knew until Sunday morning."),
    ("s06", (), "Every one of your six vans gets a sensor on one dashboard. Refunds hit about 3% of boxes."),
    ("s07", (), "About $500 a month covers five walk-ins. About $500 a month covers five vans and two walk-ins."),
    ("s09", (), "With about 20 thousand set aside the partners meet on the 20th of October, by the twentieth."),
    ("deal-3", (), "Net 45 works, and 1,260 dollars a month is the software. Twelve hundred and sixty a month too."),
    ("deal-3", (), "In 2026 we installed 2.5k sensors. A hundred trucks? Nine percent off is a price break."),
]
PHRASES = [("next Tuesday at ten", "2026-09-08"), ("next Wednesday", "2026-09-08"), ("by Thursday", "2026-09-22"),
           ("Wednesday the 30th", "2026-09-22"), ("the thirtieth", "2026-09-22"), ("October 2", "2026-09-22"),
           ("October second", "2026-09-22"), ("the week of the 19th", "2026-09-22"),
           ("the first of November", "2026-09-22"), ("the twenty-first", "2026-09-22"), ("tomorrow", "2026-09-30"),
           ("today", "2026-09-30"), ("next quarter", "2026-09-22"), ("January 15", "2026-12-01"),
           ("February 30", "2026-01-10"), ("Tuesday", "2026-09-22"), ("next Monday", "2026-09-29"),
           ("2026-10-02", "2026-09-22"), ("the 31st", "2026-09-22")]


def main():
    planted = json.loads(HERE.joinpath("evals", "planted_claims.json").read_text(encoding="utf-8"))["claims"]
    clean = json.loads(HERE.joinpath("evals", "clean_emails.json").read_text(encoding="utf-8"))["emails"]
    raw = [(p["call"], (), p["sentence"]) for p in planted] + \
          [(e["call"], tuple(e["approved"]), e["text"]) for e in clean] + EXTRA
    from agents import inputs
    tables, built_from, cases = {}, {}, []
    for call, approved, text in raw:
        name = call + ("+" + ",".join(approved) if approved else "")
        if name not in tables:
            tables[name] = key.table(call, approved)
            s = key.spec(call)
            built_from[name] = {"facts": key.facts(call), "day": s["date"], "people": inputs.roster(s),
                                "companies": inputs.companies(s), "transcript": "\n".join(key.lines(call).values()),
                                "approved": list(approved)}
        cases.append({"table": name, "text": text, "result": claims.check_email(text, tables[name])})
    out = {"lexicon": claims.lexicon(), "tables": tables, "inputs": built_from, "cases": cases,
           "dates": [{"phrase": p, "day": d, "value": (lambda r: r.isoformat() if r else None)(dates.resolve(p, d))}
                     for p, d in PHRASES]}
    path = HERE.joinpath("tests", "vectors", "claims.json")
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    n = sum(len(s["claims"]) for c in cases for s in c["result"])
    print(f"Wrote {len(cases)} cases with {n} claims, {len(tables)} tables and {len(PHRASES)} dates to "
          f"tests/vectors/claims.json")


if __name__ == "__main__":
    main()
