"""Find when each person speaks, from their own track, with an energy pass over 20 ms frames.

    .venv/bin/python3 engine/vad.py                 every call with tracks (owner/make_audio.sh runs it)
    .venv/bin/python3 engine/vad.py --calls deal-1

A frame counts as speech when it's 4 dB over the track's noise floor (its quietest tenth) and louder than -55 dBFS.
Gaps under 1.2 seconds are filled, so the pauses between one person's sentences don't split a turn, and bursts under
0.12 seconds are dropped. Each stretch then gains 30 ms before and 80 ms after, the same room the mixer leaves around
every line, so both sides measure a turn the same way. The stretches go to data/vad/<call>.json. The transcription
hears only these stretches, since Whisper invents words in long silences, and the coaching timings come from them,
since Whisper's word times drift. It never reads the mixer's ground truth. evals/timing.py compares the two
afterwards.

The first settings (15 dB over the floor, -50 dBFS, half-second gaps, no edges) set a higher bar on the buyers' phone
tracks, whose hiss raises the floor, and undercounted the buyers. These four numbers were chosen on the four tuning
calls alone and then checked on the other eight (DECISIONS.md).
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import wavio  # noqa: E402

FRAME = 0.02
GAP = 1.2
MIN_SPEECH = 0.12
OVER_FLOOR = 4.0
FLOOR_MIN = -55.0
EDGE_BEFORE = 0.03
EDGE_AFTER = 0.08


def stretches(levels, frame=FRAME):
    """[(start, end)] in seconds where the levels hold speech, with the floor and threshold used."""
    if not levels:
        return [], None, None
    dbs = [wavio.db(v) for v in levels]
    floor = sorted(dbs)[int(0.10 * (len(dbs) - 1))]
    threshold = max(floor + OVER_FLOOR, FLOOR_MIN)
    runs, start = [], None
    for i, d in enumerate(dbs):
        if d > threshold and start is None:
            start = i
        elif d <= threshold and start is not None:
            runs.append([start, i])
            start = None
    if start is not None:
        runs.append([start, len(dbs)])
    gap, keep = int(round(GAP / frame)), int(round(MIN_SPEECH / frame))
    merged = []
    for run in runs:
        if merged and run[0] - merged[-1][1] < gap:
            merged[-1][1] = run[1]
        else:
            merged.append(run)
    end = len(dbs) * frame
    out = [(round(max(0.0, s * frame - EDGE_BEFORE), 2), round(min(end, e * frame + EDGE_AFTER), 2))
           for s, e in merged if e - s >= keep]
    return out, round(floor, 1), round(threshold, 1)


def run_call(call):
    raw_dir = HERE.joinpath("data", "raw", call)
    tracks, levels = {}, {}
    for path in sorted(raw_dir.glob("*.wav")):
        if path.stem in ("mix",) or path.stem.endswith(".clean"):
            continue
        raw, rate = wavio.read(path)
        found, floor, threshold = stretches(wavio.frame_levels(raw, rate, FRAME))
        tracks[path.stem] = [list(s) for s in found]
        levels[path.stem] = {"floor_db": floor, "threshold_db": threshold,
                             "talk_s": round(sum(e - s for s, e in found), 2)}
    if not tracks:
        raise SystemExit(f"{call}: no person tracks in data/raw/{call}/. Run owner/make_audio.sh first.")
    out = HERE.joinpath("data", "vad", f"{call}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"call": call, "frame_s": FRAME, "gap_s": GAP, "min_speech_s": MIN_SPEECH,
                               "tracks": tracks, "levels": levels}, indent=1), encoding="utf-8")
    talk = ", ".join(f"{k} {v['talk_s']:.0f} s" for k, v in levels.items())
    print(f"  {call}: {talk}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--calls", default="")
    a = ap.parse_args(argv)
    names = [c for c in a.calls.split(",") if c]
    calls = names or sorted(p.name for p in HERE.joinpath("data", "raw").iterdir() if p.is_dir())
    print(f"Finding speech in {len(calls)} calls")
    for call in calls:
        run_call(call)


if __name__ == "__main__":
    main()
