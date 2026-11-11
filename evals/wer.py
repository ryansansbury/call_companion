"""Word error rate: how far each transcript is from the words the script actually said.

    python3 evals/wer.py            every call with a transcript, into evals/wer.json

Each person is voiced on a separate track and transcribed separately, so the reference for a track is that person's
script lines in order (a cut line only up to where it's cut) and the hypothesis is that track's transcript. Both are
evened out first, so "fourteen thousand dollars" and "$14,000 dollars" agree and only real mistakes count. The buyers'
tracks are also transcribed from the clean audio before the phone line, which shows what the phone line costs.
WER is (substitutions + deletions + insertions) / reference words. Standard library only.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine.align import canon  # noqa: E402
from evals import key  # noqa: E402
from generate import scripts  # noqa: E402
from generate.validate import heard  # noqa: E402


def edits(ref, hyp):
    """The word-level edit distance between two lists of words."""
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1]


def reference(call):
    """Each speaker's words, in order, as the script has them heard."""
    out = {}
    for t in scripts.load(HERE.joinpath("calls", "scripts", f"{call}.md")):
        out.setdefault(t["speaker"], []).extend(canon(" ".join(heard(t))).split())
    return out


def side_of(call):
    s = key.spec(call)
    from agents import inputs
    return {p["code"]: p["side"] for p in inputs.people(s)}


def score_call(call, transcript):
    ref, sides = reference(call), side_of(call)
    rows = {}
    for code, words in ref.items():
        hyp = canon(" ".join(w["w"] for w in transcript["tracks"].get(code, []))).split()
        row = {"side": sides.get(code), "words": len(words), "errors": edits(words, hyp)}
        clean = transcript.get("clean_tracks", {}).get(code)
        if clean is not None:
            row["clean_errors"] = edits(words, canon(" ".join(w["w"] for w in clean)).split())
        rows[code] = row
    return rows


def rate(errors, words):
    return round(errors / words, 4) if words else None


def summarize(per_call):
    tot = {"words": 0, "errors": 0, "seller_words": 0, "seller_errors": 0, "buyer_words": 0, "buyer_errors": 0,
           "buyer_clean_errors": 0, "buyer_clean_words": 0}
    for rows in per_call.values():
        for r in rows.values():
            tot["words"] += r["words"]
            tot["errors"] += r["errors"]
            side = r["side"] or "buyer"
            tot[f"{side}_words"] += r["words"]
            tot[f"{side}_errors"] += r["errors"]
            if "clean_errors" in r:
                tot["buyer_clean_words"] += r["words"]
                tot["buyer_clean_errors"] += r["clean_errors"]
    return {"overall": rate(tot["errors"], tot["words"]), "seller": rate(tot["seller_errors"], tot["seller_words"]),
            "buyer_phone": rate(tot["buyer_errors"], tot["buyer_words"]),
            "buyer_clean": rate(tot["buyer_clean_errors"], tot["buyer_clean_words"]), "words": tot["words"]}


def main():
    src = HERE.joinpath("data", "transcripts")
    calls = sorted(p.stem for p in src.glob("*.json"))
    if not calls:
        raise SystemExit("No transcripts in data/transcripts/. Run owner/transcribe.sh first.")
    per_call = {}
    for call in calls:
        transcript = json.loads(src.joinpath(f"{call}.json").read_text(encoding="utf-8"))
        per_call[call] = score_call(call, transcript)
    out = {"calls": {c: {"rows": r, **summarize({c: r})} for c, r in per_call.items()}, **summarize(per_call)}
    HERE.joinpath("evals", "wer.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    for c, v in out["calls"].items():
        print(f"  {c}: {v['overall']:.1%} overall, seller {v['seller']:.1%}, buyer {v['buyer_phone']:.1%} on the phone"
              + (f", {v['buyer_clean']:.1%} clean" if v["buyer_clean"] is not None else ""))
    print(f"All calls: {out['overall']:.1%} over {out['words']} words")


if __name__ == "__main__":
    main()
