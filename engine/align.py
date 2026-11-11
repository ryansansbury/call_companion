"""Line up the answer key with what the transcript heard.

    python3 engine/align.py            every call with a transcript, into data/key/
    python3 engine/align.py --dev      the development transcripts, into data/dev_key/ (a preview only)

The mixer records when every script line plays (data/mix/<call>.json). A line's segments are the transcript segments
on the same speaker's track that overlap it in time. A key fact sits on one or two lines, so it gets their segments,
and it counts as heard when its key terms are in their text once case, punctuation and numbers are evened out
("five thousand a month" and "$5,000 a month" both read "5000 a month"). The scorer credits an extracted item that
cites one of a fact's segments. Standard library only.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import numerals as numbers, segments  # noqa: E402


ORDINAL = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
           "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15,
           "sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19, "twentieth": 20, "thirtieth": 30}
TENS = {"twenty": 20, "thirty": 30}
ORDINAL_WORDS = re.compile(r"\b(?:(twenty|thirty)[\s-]+)?(" + "|".join(ORDINAL) + r")\b")


def canon(text):
    """Lowercase words with every number as digits, for comparing a script with a transcript. Ordinals count too, so
    "October second," "October 2nd" and "the second of October" all read as the number 2, and a thousands comma
    still joins when the transcript leaves a space before it ("$5 ,000")."""
    t = (text or "").lower().replace("’", "'").replace("%", " percent ")
    t = re.sub(r"(\d)\s*,(\d{3})\b", r"\1\2", t)
    t = re.sub(r"(\d)\s*,(\d{3})\b", r"\1\2", t)
    t = re.sub(r"\b(\d+)(?:st|nd|rd|th)\b", r"\1", t)
    t = ORDINAL_WORDS.sub(lambda m: str(TENS.get(m.group(1), 0) + ORDINAL[m.group(2)]), t)
    t = re.sub(r"[^a-z0-9.' -]+", " ", t)
    t = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", t)
    parts, last = [], 0
    for value, s, e in numbers.spoken(t):
        parts.append(t[last:s])
        parts.append(f" {value:g} ")
        last = e
    parts.append(t[last:])
    words = []
    for w in "".join(parts).replace("-", " ").split():
        w = w.strip("'")
        w = w[:-2] if w.endswith("'s") else w.replace("'", "")
        if w:
            words.append(w)
    return " ".join(words)


def has_terms(text, terms):
    """The terms not found in the text, once both are evened out. A hyphen already reads as a space, and a term of
    eight letters or more is also found with every space closed up, so "pickups" finds "pick-ups" and "Frostgauge"
    finds "Frost Gauge"."""
    have = f" {canon(text)} "
    closed = have.replace(" ", "")
    out = []
    for t in terms:
        c = canon(t)
        squeezed = c.replace(" ", "")
        if f" {c} " in have or (len(squeezed) >= 8 and squeezed in closed):
            continue
        out.append(t)
    return out


def line_segments(turns, segs):
    """Each script line's segments: same speaker, overlapping in time by at least 0.15 s or half the line."""
    out = {}
    for t in turns:
        need = min(0.15, (t["end"] - t["start"]) / 2)
        out[t["id"]] = [g["id"] for g in segs if g["speaker"] == t["speaker"] and
                        min(t["end"], g["end"]) - max(t["start"], g["start"]) >= need]
    return out


def align(spec, turns, segs):
    by_line = line_segments(turns, segs)
    text = {g["id"]: g["text"] for g in segs}
    order = {g["id"]: i for i, g in enumerate(segs)}

    def place(item, what):
        lines = item.get("lines") or [item["line"]]
        ids = sorted({x for ln in lines for x in by_line.get(ln, [])}, key=order.get)
        missing = has_terms(" ".join(text[x] for x in ids), item.get("terms", [])) if ids else item.get("terms", [])
        out = {"id": item["id"], "field": what or item["field"], "value": item.get("value") or item.get("what"),
               "lines": lines, "terms": item.get("terms", []), "segments": ids, "heard": bool(ids) and not missing,
               "missing": missing}
        for k in ("number", "unit", "date", "kind", "by", "who", "approved", "policy"):
            if item.get(k) is not None:
                out[k] = item[k]
        if what:
            out["date"] = item.get("due")
        return out
    return {"call": spec["id"], "facts": [place(f, None) for f in spec["facts"]],
            "commitments": [place(k, "commitments") for k in spec.get("commitments", [])],
            "absent": spec.get("absent", [])}


def run(call, dev=False):
    spec = json.loads(HERE.joinpath("calls", "specs", f"{call}.json").read_text(encoding="utf-8"))
    if dev:
        transcript = json.loads(HERE.joinpath("data", "dev_transcripts", f"{call}.json").read_text(encoding="utf-8"))
        turns = transcript["turns"]
    else:
        transcript = json.loads(HERE.joinpath("data", "transcripts", f"{call}.json").read_text(encoding="utf-8"))
        turns = json.loads(HERE.joinpath("data", "mix", f"{call}.json").read_text(encoding="utf-8"))["turns"]
    out = align(spec, turns, segments.from_transcript(transcript))
    out["source"] = "dev" if dev else "transcript"
    folder = HERE.joinpath("data", "dev_key" if dev else "key")
    folder.mkdir(parents=True, exist_ok=True)
    folder.joinpath(f"{call}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--calls", default="")
    a = ap.parse_args(argv)
    src = HERE.joinpath("data", "dev_transcripts" if a.dev else "transcripts")
    calls = [c for c in a.calls.split(",") if c] or sorted(p.stem for p in src.glob("*.json"))
    if not calls:
        raise SystemExit(f"No transcripts in {src.relative_to(HERE)}. Run owner/transcribe.sh first.")
    unplaced = misheard = total = 0
    for call in calls:
        out = run(call, a.dev)
        items = out["facts"] + out["commitments"]
        total += len(items)
        lost = [x for x in items if not x["segments"]]
        wrong = [x for x in items if x["segments"] and not x["heard"]]
        unplaced += len(lost)
        misheard += len(wrong)
        print(f"  {call}: {len(items) - len(lost)}/{len(items)} key items placed, {len(wrong)} with a word misheard")
        for x in lost:
            print(f"    {x['id']} {x['field']}: no segment overlaps its line")
        for x in wrong:
            print(f"    {x['id']} {x['field']}: the transcript doesn't hold {', '.join(x['missing'])}")
    # A fact that can't be placed stops everything, since scoring credits an item by the segment it cites. A word the
    # transcriber got wrong leaves the fact placed and scorable, and it's a transcription error the page reports.
    if unplaced:
        print(f"{unplaced} of {total} key items can't be placed in the transcripts.")
        return 1
    print(f"Every one of the {total} key items is placed." +
          (f" The transcriber got a key word wrong in {misheard} of them." if misheard else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
