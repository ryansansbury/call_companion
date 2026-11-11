"""The owner's machine only. Voice the scripts line by line with Kokoro-82M, the model the 11/7 research chose.

    .venv/bin/python3 audio/tts.py --warmup          one short line, so the model downloads during bootstrap
    .venv/bin/python3 audio/tts.py --samples         each deal role in its candidate voices, to pick from
    .venv/bin/python3 audio/tts.py                   every line of every call
    .venv/bin/python3 audio/tts.py --calls deal-1    only the calls named

Each line goes to data/raw/<call>/lines/<line id>.wav at the model's 24 kHz. A line already voiced with the same
voice, speed and words is skipped, so a stopped run can simply start again. Only the model's stock voices are used,
never a clone of anyone. The scripts write numbers as words, so the voice says them the way a person would.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from audio import phone  # noqa: E402
from generate import scripts  # noqa: E402

RATE = 24000
OUT = HERE.joinpath("owner", "out")
_pipes = {}


def pipeline(voice):
    """One Kokoro pipeline per accent: American for af_ and am_ voices, British for bf_ and bm_."""
    from kokoro import KPipeline
    code = "b" if voice.startswith("b") else "a"
    if code not in _pipes:
        try:
            _pipes[code] = KPipeline(lang_code=code, repo_id="hexgrad/Kokoro-82M")
        except TypeError:
            _pipes[code] = KPipeline(lang_code=code)
    return _pipes[code]


def speak(text, voice, speed=1.0):
    """The line as a float32 array at 24 kHz."""
    parts = []
    for result in pipeline(voice)(text, voice=voice, speed=speed, split_pattern=r"\n+"):
        audio = getattr(result, "audio", None)
        if audio is None:
            audio = result[2]
        if audio is None:
            continue
        audio = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
        parts.append(audio.astype(np.float32).reshape(-1))
    if not parts:
        raise RuntimeError(f"The voice model returned no audio for: {text[:60]}")
    return np.concatenate(parts)


def warmup():
    OUT.mkdir(parents=True, exist_ok=True)
    audio = speak("This is a quick test of the Call Companion voices.", "af_heart")
    sf.write(OUT.joinpath("warmup.wav"), audio, RATE, subtype="PCM_16")
    print(f"Voice model ready: {len(audio) / RATE:.1f} seconds written to owner/out/warmup.wav")


def samples():
    cast = json.loads(HERE.joinpath("calls", "cast.json").read_text(encoding="utf-8"))
    folder = OUT.joinpath("samples")
    folder.mkdir(parents=True, exist_ok=True)
    index = ["# Voice samples for G4", "",
             "Each deal role says its sample line in three stock voices. Buyer roles are also heard down the phone",
             "line, the way they'll sound in the calls. Reply with one voice per role, like AE am_michael.", ""]
    for role, person in cast["deal"].items():
        index.append(f"## {role}, {person['name']} ({person['role']}, {person['company']})")
        for n, voice in enumerate(person["candidates"]):
            path = folder.joinpath(f"{role}-{voice}.wav")
            sf.write(path, speak(person["sample"], voice, person.get("speed", 1.0)), RATE, subtype="PCM_16")
            line = f"- {path.name}"
            if person["side"] == "buyer":
                heard = folder.joinpath(f"{role}-{voice}-phone.wav")
                phone.phone_line(path, heard, seed=n)
                line += f" (and {heard.name})"
            index.append(line)
            print(f"  {role} {voice}")
        index.append("")
    folder.joinpath("INDEX.md").write_text("\n".join(index), encoding="utf-8")
    print(f"Samples written to {folder.relative_to(HERE)}. Open the folder with: open owner/out/samples")


def voices_for(spec, cast):
    """Speaker code to (voice, speed) for one call: the deal's cast, or the people in a scored call's spec."""
    people = cast["deal"] if spec["kind"] == "deal" else spec["cast"]
    out = {}
    for code, person in people.items():
        if not person.get("voice"):
            raise SystemExit(f"{spec['id']}: no voice set for {code}. Pick the voices first.")
        out[code] = (person["voice"], person.get("speed", 1.0))
    return out


def voice_call(spec, cast):
    folder = HERE.joinpath("data", "raw", spec["id"], "lines")
    folder.mkdir(parents=True, exist_ok=True)
    index_path = folder.joinpath("index.json")
    done = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    voices = voices_for(spec, cast)
    turns = scripts.load(HERE.joinpath("calls", "scripts", f"{spec['id']}.md"))
    made = 0
    for turn in turns:
        voice, speed = voices[turn["speaker"]]
        key = hashlib.sha256(f"{voice}|{speed}|{turn['text']}".encode()).hexdigest()[:16]
        path = folder.joinpath(f"{turn['id']}.wav")
        if done.get(turn["id"]) == key and path.exists():
            continue
        sf.write(path, speak(turn["text"], voice, speed), RATE, subtype="PCM_16")
        done[turn["id"]] = key
        made += 1
    index_path.write_text(json.dumps(done, indent=1), encoding="utf-8")
    print(f"  {spec['id']}: {len(turns)} lines, {made} voiced now")


def specs(names=None):
    found = sorted(HERE.joinpath("calls", "specs").glob("*.json"))
    loaded = [json.loads(p.read_text(encoding="utf-8")) for p in found]
    return [s for s in loaded if not names or s["id"] in names]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--warmup", action="store_true")
    ap.add_argument("--samples", action="store_true")
    ap.add_argument("--calls", default="")
    a = ap.parse_args(argv)
    if a.warmup:
        return warmup()
    if a.samples:
        return samples()
    cast = json.loads(HERE.joinpath("calls", "cast.json").read_text(encoding="utf-8"))
    chosen = specs([c for c in a.calls.split(",") if c])
    if not chosen:
        raise SystemExit("No call specs found in calls/specs/.")
    print(f"Voicing {len(chosen)} calls with Kokoro-82M")
    for spec in chosen:
        voice_call(spec, cast)


if __name__ == "__main__":
    main()
