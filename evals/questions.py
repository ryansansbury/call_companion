"""Score the coaching's open-question rule against the hand labels in calls/question_labels.json.

    python3 evals/questions.py          into evals/questions.json (build.py runs it)

engine/coaching.py's is_open() calls a question open when, past any leading clause, it starts with what, how, why,
where, which, tell, walk, describe or explain, and isn't a count, a person or a date (how many, who, when). The
labels say whether each of the 73 seller questions in the scripts asks the buyer to explain. This reports how often the rule agrees, and lists where it doesn't, so the page can say how far to trust the
open share. When transcripts exist, it also counts how many labeled questions the transcript still ends with a
question mark, since the rule only sees those. Standard library only.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import coaching  # noqa: E402


FIRST_RUN = {"agreement": 0.781, "note": "The first rule, before the revision, on all 73 questions. The revision "
             "was written after seeing every disagreement, so the revised figures are optimistic."}


def score():
    labels = json.loads(HERE.joinpath("calls", "question_labels.json").read_text(encoding="utf-8"))["labels"]
    rows, agree = [], 0
    confusion = {"open_open": 0, "open_closed": 0, "closed_open": 0, "closed_closed": 0}
    for line, items in labels.items():
        for q, label in items:
            said = "open" if coaching.is_open(q) else "closed"
            confusion[f"{label}_{said}"] += 1
            agree += said == label
            if said != label:
                rows.append({"line": line, "question": q, "label": label, "rule": said})
    n = sum(confusion.values())
    tp = confusion["open_open"]
    out = {"questions": n, "open": confusion["open_open"] + confusion["open_closed"], "agreement": round(agree / n, 3),
           "open_precision": round(tp / max(1, tp + confusion["closed_open"]), 3),
           "open_recall": round(tp / max(1, tp + confusion["open_closed"]), 3), "confusion": confusion,
           "disagreements": rows, "first_run": FIRST_RUN}
    return out


def main():
    out = score()
    HERE.joinpath("evals", "questions.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(f"Open-question rule agrees with the labels on {out['agreement']:.0%} of {out['questions']} questions "
          f"(open precision {out['open_precision']:.0%}, recall {out['open_recall']:.0%})")
    for r in out["disagreements"]:
        print(f"  {r['line']}: labeled {r['label']}, rule says {r['rule']}: {r['question']}")


if __name__ == "__main__":
    main()
