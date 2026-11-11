"""Waveform peaks for the player's lanes: ten per second for each person, as one short string per track.

    .venv/bin/python3 engine/peaks.py               every call with tracks (owner/make_audio.sh runs it)

Each 100 ms window keeps its loudest sample, scaled against the loudest window in the whole call so the lanes share
one scale, and stored as one character from a 62-letter alphabet. A five-minute call with three people comes to about
9 KB, which keeps the page light. Results go to data/peaks/<call>.json, which the bundle reads.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import wavio  # noqa: E402

RATE_PER_S = 10
ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def encode(levels, top):
    """Levels as characters, 0 for silence up to z for the loudest window of the call."""
    steps = len(ALPHABET) - 1
    top = top or 1.0
    return "".join(ALPHABET[min(steps, int(round(steps * (v / top) ** 0.6)))] for v in levels)


def decode(text):
    steps = len(ALPHABET) - 1
    return [ALPHABET.index(c) / steps for c in text]


def run_call(call):
    raw_dir = HERE.joinpath("data", "raw", call)
    levels, duration = {}, 0.0
    for path in sorted(raw_dir.glob("*.wav")):
        if path.stem == "mix" or path.stem.endswith(".clean"):
            continue
        raw, rate = wavio.read(path)
        levels[path.stem] = wavio.frame_levels(raw, rate, 1.0 / RATE_PER_S, kind="peak")
        duration = max(duration, len(raw) / 2 / rate)
    top = max((max(v) for v in levels.values() if v), default=1.0)
    out = HERE.joinpath("data", "peaks", f"{call}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"call": call, "per_s": RATE_PER_S, "duration_s": round(duration, 2),
                               "tracks": {k: encode(v, top) for k, v in levels.items()}}), encoding="utf-8")
    print(f"  {call}: {len(levels)} lanes, {duration:.0f} s")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--calls", default="")
    a = ap.parse_args(argv)
    names = [c for c in a.calls.split(",") if c]
    calls = names or sorted(p.name for p in HERE.joinpath("data", "raw").iterdir() if p.is_dir())
    for call in calls:
        run_call(call)


if __name__ == "__main__":
    main()
