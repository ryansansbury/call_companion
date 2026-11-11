"""The owner's machine only. Mix each call from its voiced lines, then make the phone line and the web encode.

    .venv/bin/python3 audio/mix.py                   every call that has its lines voiced
    .venv/bin/python3 audio/mix.py --calls deal-1

Each line is trimmed to its voice first, since the voice model pads every line with silence, so a scripted pause is
the real silence between two voices and each turn's time is when that person is actually speaking. Each line then
goes on its speaker's own track at the time the script's marks set:
- the gap before a line is its {pause}, or about 0.35 seconds with a small seeded jitter;
- {overlap s} starts a line that many seconds before the previous one ends;
- a line after one marked {cut n} starts at the estimated end of that line's nth word, and the cut line fades out
  0.4 seconds later, the way a person stops when someone talks over them;
- {bc s} puts a backchannel s seconds into the previous line, on the listener's track, without moving the clock.

It writes one WAV per person to data/raw/<call>/ (buyers twice, clean and down the phone line), the mixed call,
data/mix/<call>.json with every turn's true start and end (the ground truth the VAD and the coaching numbers are
scored against), and the web encode in site/audio/<call>.v1.m4a: AAC, mono, 48 kbps at 24 kHz, loudness near
-16 LUFS.
"""
import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from audio import phone  # noqa: E402
from generate import scripts  # noqa: E402

RATE = 24000
LEAD_IN = 0.6
TAIL = 0.8
FADE_AFTER = 0.4
FADE = 0.15
VERSION = "v1"
EDGE_DB = -55.0
KEEP_BEFORE = 0.03
KEEP_AFTER = 0.08


def trim(a):
    """The line from just before its first sound to just after its last. The voice model pads every line with half
    a second or more of silence, which would sit on top of each scripted pause and count as talking in the ground
    truth. A little room stays on both sides so no consonant or breath gets clipped."""
    hop = RATE // 100
    frames = len(a) // hop
    if frames == 0:
        return a
    rms = np.sqrt(np.mean(a[:frames * hop].reshape(frames, hop) ** 2, axis=1))
    voiced = np.flatnonzero(rms > 10 ** (EDGE_DB / 20))
    if voiced.size == 0:
        return a
    start = max(0, voiced[0] * hop - int(KEEP_BEFORE * RATE))
    end = min(len(a), (voiced[-1] + 1) * hop + int(KEEP_AFTER * RATE))
    return a[start:end]


def word_end(turn, n, duration):
    """Estimated time the nth word ends: its share of the line's letters, which is close enough for a cut."""
    words = turn["words"]
    if n >= len(words):
        return duration
    letters = [len(w) + 1 for w in words]
    return duration * sum(letters[:n]) / sum(letters)


def side_of(spec, cast, code):
    people = cast["deal"] if spec["kind"] == "deal" else spec["cast"]
    return people[code]["side"]


def plan(spec, turns, durations):
    """Every turn's start, audible end and fade, from the marks. Returns the turns in order with times."""
    rng = random.Random(spec["id"])
    placed, t, prev, prev_main = [], LEAD_IN, None, None
    for turn in turns:
        d = durations[turn["id"]]
        m = turn["marks"]
        if "bc" in m and prev_main is not None:
            start = prev_main["start"] + m["bc"]
            placed.append({**turn, "start": start, "end": start + d, "audible_end": start + d, "bc": True})
            continue
        if prev_main is not None and prev_main["marks"].get("cut"):
            start = prev_main["start"] + word_end(prev_main, prev_main["marks"]["cut"], prev_main["dur"])
            prev_main["audible_end"] = min(prev_main["end"], start + FADE_AFTER + FADE)
            prev_main["fade_at"] = start + FADE_AFTER
        elif "overlap" in m and prev_main is not None:
            start = max(prev_main["start"] + 0.2, prev_main["end"] - m["overlap"])
        else:
            gap = m["pause"] if "pause" in m else 0.35
            gap = max(0.12, gap + rng.uniform(-0.08, 0.08))
            start = prev_main["audible_end"] + gap if prev_main else t
        item = {**turn, "start": start, "end": start + d, "audible_end": start + d, "dur": d, "bc": False}
        placed.append(item)
        prev_main = item
    return placed


def build_call(spec, cast):
    call = spec["id"]
    raw = HERE.joinpath("data", "raw", call)
    turns = scripts.load(HERE.joinpath("calls", "scripts", f"{call}.md"))
    audio = {}
    for turn in turns:
        path = raw.joinpath("lines", f"{turn['id']}.wav")
        if not path.exists():
            raise SystemExit(f"{call}: {turn['id']} isn't voiced yet. Run audio/tts.py first.")
        a, rate = sf.read(path, dtype="float32")
        if rate != RATE:
            raise SystemExit(f"{call}: {turn['id']} is {rate} Hz, not {RATE}.")
        audio[turn["id"]] = trim(a)
    durations = {k: len(v) / RATE for k, v in audio.items()}
    placed = plan(spec, turns, durations)
    total = max(p["end"] for p in placed) + TAIL
    n = int(total * RATE) + 1
    tracks = {}
    for p in placed:
        track = tracks.setdefault(p["speaker"], np.zeros(n, dtype=np.float32))
        a = audio[p["id"]].copy()
        if "fade_at" in p:
            cut = int((p["fade_at"] - p["start"]) * RATE)
            fade = int(FADE * RATE)
            if 0 < cut < len(a):
                ramp = np.linspace(1.0, 0.0, min(fade, len(a) - cut), dtype=np.float32)
                a[cut:cut + len(ramp)] *= ramp
                a[cut + len(ramp):] = 0.0
        s = int(p["start"] * RATE)
        track[s:s + len(a)] += a[:max(0, n - s)]
    for code, track in tracks.items():
        sf.write(raw.joinpath(f"{code}.wav"), np.clip(track, -1, 1), RATE, subtype="PCM_16")
    mixed = np.zeros(n, dtype=np.float32)
    for i, (code, track) in enumerate(sorted(tracks.items())):
        path = raw.joinpath(f"{code}.wav")
        if side_of(spec, cast, code) == "buyer":
            clean = raw.joinpath(f"{code}.clean.wav")
            path.replace(clean)
            phone.phone_line(clean, path, seed=i + 1)
        heard, _ = sf.read(path, dtype="float32")
        mixed[:len(heard)] += heard[:n]
    peak = float(np.max(np.abs(mixed))) or 1.0
    if peak > 0.99:
        mixed *= 0.99 / peak
    sf.write(raw.joinpath("mix.wav"), mixed, RATE, subtype="PCM_16")

    truth = {"call": call, "rate": RATE, "length_s": round(total, 3), "version": VERSION,
             "turns": [{"id": p["id"], "speaker": p["speaker"], "start": round(p["start"], 3),
                        "end": round(p["audible_end"], 3), "voiced_end": round(p["end"], 3),
                        "bc": p["bc"], "cut": p["marks"].get("cut")} for p in placed]}
    mix_dir = HERE.joinpath("data", "mix")
    mix_dir.mkdir(parents=True, exist_ok=True)
    mix_dir.joinpath(f"{call}.json").write_text(json.dumps(truth, indent=1), encoding="utf-8")

    site = HERE.joinpath("site", "audio")
    site.mkdir(parents=True, exist_ok=True)
    out = site.joinpath(f"{call}.{VERSION}.m4a")
    done = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw.joinpath("mix.wav")),
                           "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", str(RATE), "-ac", "1",
                           "-c:a", "aac", "-b:a", "48k", "-movflags", "+faststart", str(out)],
                          capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit(f"{call}: the encode failed: {done.stderr.strip()[-300:]}")
    print(f"  {call}: {total:.0f} s, {len(tracks)} tracks, {out.stat().st_size // 1024} KB encoded")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--calls", default="")
    a = ap.parse_args(argv)
    cast = json.loads(HERE.joinpath("calls", "cast.json").read_text(encoding="utf-8"))
    names = [c for c in a.calls.split(",") if c]
    specs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(HERE.joinpath("calls", "specs").glob("*.json"))]
    specs = [s for s in specs if not names or s["id"] in names]
    print(f"Mixing {len(specs)} calls")
    for spec in specs:
        build_call(spec, cast)


if __name__ == "__main__":
    main()
