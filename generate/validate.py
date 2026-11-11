"""Check every call spec against its script before anything is voiced.

    python3 generate/validate.py            every call
    python3 generate/validate.py deal-1     one call

For each call it checks that every fact and commitment sits on the line the spec names, with its number and key terms
in the words a listener actually hears (a line cut off by an interruption counts only up to the cut), that nothing the
key needs is a backchannel, that every field is either keyed or marked absent, that the seller's share of the words
is within five points of the rep profile, and that the call fits its target length. It prints one line per call and
exits 1 on any problem, so the build and the freeze refuse a broken key.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import numerals as numbers  # noqa: E402
from generate import scripts  # noqa: E402

FIELDS = ["metrics", "economic_buyer", "decision_criteria", "decision_process", "paper_process", "pain", "champion",
          "competition", "critical_event", "budget", "pricing", "amount", "close_date", "next_steps", "stakeholders",
          "risks", "account", "seller_claims"]
WPM = 150


def flat(text):
    """Lowercase words only, so "load-out," "warm-delivery" and "can't" compare the same in a term and a line."""
    words = scripts.words(text.lower().replace("-", " ").replace("’", "'"))
    return " ".join(w[:-2] if w.endswith("'s") else w.replace("'", "") for w in words)


def heard(turn):
    """The words a listener hears: a line cut off after its nth word keeps only those."""
    n = turn["marks"].get("cut")
    return turn["words"][:n] if n else turn["words"]


def people_for(spec, cast):
    return cast["deal"] if spec["kind"] == "deal" else spec["cast"]


def check(spec, cast):
    problems = []
    turns = scripts.load(HERE.joinpath("calls", "scripts", f"{spec['id']}.md"))
    ids = [t["id"] for t in turns]
    if len(set(ids)) != len(ids):
        problems.append("duplicate line ids")
    if ids != sorted(ids):
        problems.append("line ids out of order")
    people = people_for(spec, cast)
    by_id = {t["id"]: t for t in turns}
    for t in turns:
        if t["speaker"] not in people:
            problems.append(f"{t['id']}: speaker {t['speaker']} isn't in the cast")

    def located(item, label):
        lines = item.get("lines") or [item["line"]]
        gone = [line for line in lines if line not in by_id]
        if gone:
            problems.append(f"{label}: no line {', '.join(gone)}")
            return
        if any("bc" in by_id[line]["marks"] for line in lines):
            problems.append(f"{label}: sits in a backchannel")
        text = " ".join(" ".join(heard(by_id[line])) for line in lines)
        if "number" in item and not numbers.has(text, item["number"]):
            problems.append(f"{label}: {item['number']} isn't heard on {', '.join(lines)}")
        low = f" {flat(text)} "
        for term in item.get("terms", []):
            if f" {flat(term)} " not in low:
                problems.append(f"{label}: '{term}' isn't heard on {', '.join(lines)}")

    for f in spec["facts"]:
        if f["field"] not in FIELDS:
            problems.append(f"{f['id']}: unknown field {f['field']}")
        located(f, f["id"])
    for k in spec.get("commitments", []):
        located(k, k["id"])

    present = {f["field"] for f in spec["facts"]}
    absent = set(spec.get("absent", []))
    for a in sorted(absent & present):
        problems.append(f"{a} is marked absent but has a fact")
    undecided = set(FIELDS) - present - absent
    if undecided:
        problems.append(f"neither keyed nor marked absent: {', '.join(sorted(undecided))}")

    seller = sum(len(heard(t)) for t in turns if people[t["speaker"]]["side"] == "seller")
    total = sum(len(heard(t)) for t in turns)
    share = seller / total if total else 0.0
    target = spec["rep"]["talk_share"]
    if abs(share - target) > 0.05:
        problems.append(f"the seller side has {share:.0%} of the words, against a profile of {target:.0%}")
    seconds = total * 60 / WPM
    if not 0.7 * spec["length_s"] <= seconds <= 1.3 * spec["length_s"]:
        problems.append(f"about {seconds:.0f} seconds of words against a target of {spec['length_s']}")
    stats = {"lines": len(turns), "words": total, "seller_share": round(share, 3), "est_seconds": round(seconds)}
    return problems, stats


def main(argv=None):
    names = set((argv if argv is not None else sys.argv[1:]))
    cast = json.loads(HERE.joinpath("calls", "cast.json").read_text(encoding="utf-8"))
    specs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(HERE.joinpath("calls", "specs").glob("*.json"))]
    specs = [s for s in specs if not names or s["id"] in names]
    bad = 0
    for spec in specs:
        problems, stats = check(spec, cast)
        head = (f"{spec['id']}: {stats['lines']} lines, {stats['words']} words, about {stats['est_seconds']} s, "
                f"seller {stats['seller_share']:.0%}, {len(spec['facts'])} facts")
        print(("ok    " if not problems else "FIX   ") + head)
        for p in problems:
            print("      - " + p)
        bad += bool(problems)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
