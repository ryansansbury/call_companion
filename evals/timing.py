"""Talk time from the voice activity detector against the mix's ground truth.

    python3 evals/timing.py         every call with VAD stretches, into evals/timing.json

The mixer knows when every line plays (data/mix/<call>.json), so the true talk time for each person is the union of
their lines. The coaching numbers use the VAD's stretches from the audio itself (data/vad/<call>.json). This compares
the seller's share of talk time both ways against a bar of two points, and it reports the four tuning calls
the VAD's settings were chosen on apart from the other eight. Standard library only.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from evals.wer import side_of  # noqa: E402

BAR = 2.0


def split_of(call):
    """dev, test or deal, from the call's spec. The VAD's settings were chosen on the dev calls alone."""
    return json.loads(HERE.joinpath("calls", "specs", f"{call}.json").read_text(encoding="utf-8")).get("split")


def union(spans):
    total, end = 0.0, None
    for s, e in sorted(spans):
        if end is None or s > end:
            total += e - s
            end = e
        elif e > end:
            total += e - end
            end = e
    return total


def shares(by_speaker, sides):
    talk = {code: union(spans) for code, spans in by_speaker.items()}
    seller = sum(v for c, v in talk.items() if sides.get(c) == "seller")
    total = sum(talk.values())
    return {"seconds": {c: round(v, 2) for c, v in talk.items()}, "seller_share": round(seller / total, 4)}


def main():
    calls = sorted(p.stem for p in HERE.joinpath("data", "vad").glob("*.json"))
    if not calls:
        raise SystemExit("No VAD stretches in data/vad/. Run owner/make_audio.sh first.")
    out, worst = {"calls": {}}, 0.0
    for call in calls:
        sides = side_of(call)
        vad = json.loads(HERE.joinpath("data", "vad", f"{call}.json").read_text(encoding="utf-8"))["tracks"]
        mix = json.loads(HERE.joinpath("data", "mix", f"{call}.json").read_text(encoding="utf-8"))
        truth = {}
        for t in mix["turns"]:
            truth.setdefault(t["speaker"], []).append((t["start"], t["end"]))
        a, b = shares(vad, sides), shares(truth, sides)
        gap = round(abs(a["seller_share"] - b["seller_share"]) * 100, 2)
        worst = max(worst, gap)
        out["calls"][call] = {"vad": a, "truth": b, "points_off": gap}
        print(f"  {call}: VAD {a['seller_share']:.1%} seller, truth {b['seller_share']:.1%}, {gap} points off")
    tuning = [c for c in calls if split_of(c) == "dev"]
    out["worst_points_off"] = worst
    out["bar_points"] = BAR
    out["passes"] = worst <= BAR
    out["tuned_on"] = tuning
    out["worst_tuning"] = max([out["calls"][c]["points_off"] for c in tuning] or [0.0])
    out["misses"] = [c for c in calls if out["calls"][c]["points_off"] > BAR]
    out["within"] = len(calls) - len(out["misses"])
    HERE.joinpath("evals", "timing.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(f"{out['within']} of {len(calls)} calls within the {BAR:g}-point bar. Worst on the tuning calls the VAD was set on "
          f"{out['worst_tuning']} points, worst overall {worst}" +
          (f", and {', '.join(out['misses'])} {'misses' if len(out['misses']) == 1 else 'miss'} it" if out["misses"] else ""))


if __name__ == "__main__":
    main()
