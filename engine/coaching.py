"""The coaching numbers, from when each person spoke and what the rep asked.

Timings come from each person's speech stretches (data/vad/<call>.json), never from the mixer's ground truth, which
evals/timing.py uses only to score them. Definitions, which the page shows:
- talk share: each person's speaking time over everyone's;
- longest monologue: the rep's longest run of speech, where the buyer's replies under two seconds ("right," "yeah")
  don't break it, and the longest customer story the same way for the buyer;
- patience: the median pause between the buyer finishing and the rep starting, skipping pauses over five seconds;
- interactivity: switches between seller and buyer per five minutes, capped at 10, with backchannels left out;
- interruptions: a person starting to talk, for more than a second, while someone on the other side is mid-stretch;
- questions: the rep's sentences that end in a question mark, and the share that are open, by is_open(), which
  evals/questions.py scores against hand labels.
"""
import json
import re
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent.parent
BACKCHANNEL = 2.0
FILLER = r"^(?:so\s+|and\s+|okay\s+|um\s+|and\s+hey,?\s+)*"
OPEN = re.compile(FILLER + r"(what|how|why|tell|walk|describe|explain|where|which)\b", re.I)
FACT = re.compile(FILLER + r"(?:how\s+(?:many|much|long|often)|who|when|what\s+if)\b", re.I)
LEAD = re.compile(r"^(?:(?:so\s+)?(?:if|before|once|now that|given)\b[^,?]*,\s*|(?:can|may)\s+i\s+ask\s+|"
                  r"could you tell me\s+|i'm curious\s+)", re.I)


def is_open(question):
    """Whether a question asks the buyer to explain. A leading clause ("If you decided this was worth doing, ...") is
    read past, and counts, people and dates ("how many," "who," "when") are closed, like a yes or no."""
    q = LEAD.sub("", question.strip(), count=1)
    return not FACT.match(q) and bool(OPEN.match(q))


def stretches_from_words(transcript, gap=0.5):
    """Speech stretches from a transcript's word times, for development previews without VAD files."""
    out = {}
    for spk, words in transcript["tracks"].items():
        runs = []
        for w in sorted(words, key=lambda x: x["start"]):
            if runs and w["start"] - runs[-1][1] < gap:
                runs[-1][1] = max(runs[-1][1], w["end"])
            else:
                runs.append([w["start"], w["end"]])
        out[spk] = runs
    return out


def _side_runs(tracks, sides, side):
    runs = sorted((s, e) for spk, rs in tracks.items() if sides[spk] == side for s, e in rs)
    merged = []
    for s, e in runs:
        if merged and s <= merged[-1][1] + 0.05:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


def _longest(mine, theirs):
    """The longest run of mine that no stretch of theirs of two seconds or more interrupts."""
    breaks = [(s, e) for s, e in theirs if e - s >= BACKCHANNEL]
    best, start, end = 0.0, None, None
    for s, e in mine:
        if start is None:
            start, end = s, e
            continue
        if any(end <= bs < s or (bs <= end < be) for bs, be in breaks if bs < s):
            best = max(best, end - start)
            start, end = s, e
        else:
            end = max(end, e)
    if start is not None:
        best = max(best, end - start)
    return round(best, 1)


def questions(segs, rep_codes):
    asked = []
    for g in segs:
        if g["speaker"] not in rep_codes:
            continue
        for sentence in re.split(r"(?<=[.?!])\s+", g["text"]):
            if sentence.strip().endswith("?"):
                asked.append({"segment": g["id"], "text": sentence.strip(),
                              "open": is_open(sentence)})
    return asked


def metrics(tracks, segs, sides, length_s):
    """Every coaching number for one call. sides maps a speaker code to seller or buyer."""
    talk = {spk: round(sum(e - s for s, e in rs), 1) for spk, rs in tracks.items()}
    total = sum(talk.values()) or 1.0
    seller = _side_runs(tracks, sides, "seller")
    buyer = _side_runs(tracks, sides, "buyer")
    pauses = []
    for bs, be in buyer:
        nxt = [s for s, _ in seller if s >= be]
        if nxt and nxt[0] - be <= 5.0 and (be - bs) >= 1.0:
            pauses.append(nxt[0] - be)
    events = sorted([(s, "seller") for s, e in seller if e - s >= BACKCHANNEL] +
                    [(s, "buyer") for s, e in buyer if e - s >= BACKCHANNEL])
    switches = sum(1 for a, b in zip(events, events[1:]) if a[1] != b[1])
    windows = max(1.0, length_s / 300.0)
    interruptions = {"seller": 0, "buyer": 0}
    for side, mine, theirs in (("seller", seller, buyer), ("buyer", buyer, seller)):
        for s, e in mine:
            if e - s < 1.0:
                continue
            if any(ts < s - 0.3 and te > s + 0.3 for ts, te in theirs):
                interruptions[side] += 1
    reps = [spk for spk, side in sides.items() if side == "seller"]
    asked = questions(segs, reps)
    return {
        "talk_s": talk,
        "talk_share": {spk: round(v / total, 3) for spk, v in talk.items()},
        "seller_share": round(sum(v for spk, v in talk.items() if sides[spk] == "seller") / total, 3),
        "longest_monologue_s": _longest(seller, buyer),
        "longest_story_s": _longest(buyer, seller),
        "patience_s": round(median(pauses), 2) if pauses else None,
        "interactivity": round(min(10.0, switches / windows), 1),
        "rep_interruptions": interruptions["seller"],
        "buyer_interruptions": interruptions["buyer"],
        "questions": len(asked),
        "questions_per_10min": round(len(asked) * 600.0 / max(60.0, length_s), 1),
        "open_share": round(sum(q["open"] for q in asked) / len(asked), 2) if asked else None,
        "asked": asked,
    }


def component(value, rule):
    """1 inside the good range, down to 0 at the bad edge, linearly."""
    if value is None:
        return None
    lo, hi = rule["good"]
    blo, bhi = rule["bad"]
    if lo <= value <= hi:
        return 1.0
    if value < lo:
        return max(0.0, 1.0 - (lo - value) / max(1e-9, lo - blo))
    return max(0.0, 1.0 - (value - hi) / max(1e-9, bhi - hi))


def score(m, rubric, weights=None):
    """The weighted score out of 100 and each component's part, skipping measures the call didn't produce."""
    parts, total_w = {}, 0.0
    for key, rule in rubric["components"].items():
        value = m.get("seller_share") if key == "talk_share" else m.get(key)
        c = component(value, rule)
        w = (weights or {}).get(key, rule["weight"])
        parts[key] = {"value": value, "score": None if c is None else round(c, 2), "weight": w}
        if c is not None:
            total_w += w
    got = sum(p["score"] * p["weight"] for p in parts.values() if p["score"] is not None)
    return {"score": round(100.0 * got / total_w) if total_w else None, "parts": parts}


def load_rubric():
    return json.loads(HERE.joinpath("config", "rubric.json").read_text(encoding="utf-8"))
