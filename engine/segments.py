"""Turn a transcript's words into numbered segments: one speaker's run of words, the unit every citation points at.

Words from all tracks are sorted by time. A segment keeps going while the same person talks with gaps under 1.2
seconds, so a backchannel from the listener starts its own short segment instead of splitting the speaker's turn. Ids
read like d1-s012 (call 1, segment 12), and each segment carries its speaker, start, end, text and the probability of
each word, which the page uses to mark uncertain words.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
JOIN_GAP = 1.2


def short(call):
    """deal-1 becomes d1, and s05 stays s05."""
    return "d" + call.split("-")[1] if call.startswith("deal-") else call


def from_transcript(transcript):
    """[{id, speaker, start, end, text, words: [{w, start, end, p}]}] in time order."""
    words = [dict(w, speaker=spk) for spk, ws in transcript["tracks"].items() for w in ws if w["w"]]
    words.sort(key=lambda w: (w["start"], w["end"]))
    open_by, segments = {}, []
    for w in words:
        seg = open_by.get(w["speaker"])
        if seg is not None and w["start"] - seg["end"] <= JOIN_GAP and segments[-1] is seg:
            seg["words"].append(w)
            seg["end"] = max(seg["end"], w["end"])
            continue
        if seg is not None and w["start"] - seg["end"] <= JOIN_GAP and _only_short_between(segments, seg):
            seg["words"].append(w)
            seg["end"] = max(seg["end"], w["end"])
            continue
        seg = {"speaker": w["speaker"], "start": w["start"], "end": w["end"], "words": [w]}
        segments.append(seg)
        open_by[w["speaker"]] = seg
    prefix = short(transcript["call"])
    out = []
    for i, seg in enumerate(sorted(segments, key=lambda s: s["start"]), 1):
        ws = joined(seg["words"])
        out.append({"id": f"{prefix}-s{i:03d}", "speaker": seg["speaker"], "start": round(seg["start"], 2),
                    "end": round(seg["end"], 2), "text": " ".join(x["w"] for x in ws).strip(),
                    "words": [{"w": x["w"], "start": x["start"], "end": x["end"], "p": x.get("p")} for x in ws]})
    return out


def joined(words):
    """Whisper hands back pieces of one written word as separate words: "$5" and ",000", "30" and "%", "pick" and
    "-ups". A piece that opens with punctuation, or with a hyphen and a letter or digit, joins the word before it, and
    the joined word keeps the lower probability."""
    out = []
    for w in words:
        t = w["w"]
        tail = t[:1] in ",.%?!;:)" or (t[:1] == "-" and t[1:2].isalnum())
        if out and tail:
            prev = out[-1]
            ps = [p for p in (prev.get("p"), w.get("p")) if p is not None]
            out[-1] = dict(prev, w=prev["w"] + t, end=max(prev["end"], w["end"]), p=min(ps) if ps else None)
        else:
            out.append(dict(w))
    return out


def _only_short_between(segments, seg):
    """True when every segment after seg is a short backchannel (under two seconds), so seg can keep going."""
    idx = next(i for i, s in enumerate(segments) if s is seg)
    return all(s["end"] - s["start"] < 2.0 and len(s["words"]) <= 3 for s in segments[idx + 1:])


def load(call):
    transcript = json.loads(HERE.joinpath("data", "transcripts", f"{call}.json").read_text(encoding="utf-8"))
    return from_transcript(transcript)
