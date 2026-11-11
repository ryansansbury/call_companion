"""Development only: a transcript-shaped file made straight from a script, for building before the real audio exists.

    python3 generate/dev_transcript.py            every call, into data/dev_transcripts/

Words get evenly spread times at about 2.6 words a second with the script's pauses, and every word a probability of
0.99. Nothing here is heard or transcribed, so these files never reach the page or the scores. build.py refuses them
for anything but a development preview, and the page labels such a preview in red.
"""
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from generate import scripts  # noqa: E402

WPS = 2.6


def make(call):
    turns = scripts.load(HERE.joinpath("calls", "scripts", f"{call}.md"))
    rng = random.Random(call)
    t, prev_start, prev_end = 0.6, 0.0, 0.0
    tracks, timed = {}, []
    for turn in turns:
        m = turn["marks"]
        words = turn["words"][:m["cut"]] if "cut" in m else turn["words"]
        dur = max(0.3, len(turn["words"]) / WPS)
        if "bc" in m:
            start = prev_start + m["bc"]
        else:
            start = (prev_end - m["overlap"]) if "overlap" in m else prev_end + m.get("pause", 0.35)
            start = max(start, 0.6)
        step = dur / max(1, len(turn["words"]))
        tokens = turn["text"].split()
        for i, w in enumerate(tokens[:len(words)]):
            s = start + i * step
            tracks.setdefault(turn["speaker"], []).append(
                {"w": w, "start": round(s, 3), "end": round(s + step * 0.9, 3), "p": round(rng.uniform(0.9, 1.0), 3)})
        heard_end = start + (len(words) / WPS if "cut" in m else dur)
        timed.append({"id": turn["id"], "speaker": turn["speaker"], "start": round(start, 3),
                      "end": round(heard_end, 3), "bc": "bc" in m})
        if "bc" not in m:
            prev_start, prev_end = start, heard_end
    return {"call": call, "tool": "dev-from-script", "model": "none", "dev": True, "tracks": tracks,
            "turns": timed}


def main():
    out_dir = HERE.joinpath("data", "dev_transcripts")
    out_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(HERE.joinpath("calls", "specs").glob("*.json")):
        call = path.stem
        out_dir.joinpath(f"{call}.json").write_text(json.dumps(make(call), indent=1), encoding="utf-8")
    print(f"Wrote development transcripts for {len(list(out_dir.glob('*.json')))} calls to data/dev_transcripts/")


if __name__ == "__main__":
    main()
