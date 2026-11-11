"""The owner's machine only. Transcribe each person's own track with mlx-whisper and large-v3-turbo, keeping word
timings and each word's probability.

    .venv/bin/python3 transcribe/stt.py --warmup       transcribes the bootstrap's warm-up line
    .venv/bin/python3 transcribe/stt.py                every call with tracks and a VAD file
    .venv/bin/python3 transcribe/stt.py --calls deal-1

Whisper fills long silences with invented phrases, so it hears only the stretches the VAD found on each
track (data/vad/<call>.json), each padded by 0.3 seconds, with the times shifted back onto the call's clock. Buyer
tracks are transcribed twice, with and without the phone line, for the word error rate comparison. Results go to
data/transcripts/<call>.json. If the words come back without a probability, it stops and says so, since the page's
uncertain-word feature depends on it.

Each call's transcription starts from a short list of names (vocabulary below), the way a deployment would give
its transcriber the account's names. The first run without it wrote the competitor Frostgauge three different
ways, which would have split one competitor into three in the CRM.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
MODEL = "mlx-community/whisper-large-v3-turbo"
SR = 16000
PAD = 0.3


def load16k(path):
    from mlx_whisper.audio import load_audio
    return load_audio(str(path))


def transcribe(audio, prompt=None):
    import mlx_whisper
    return mlx_whisper.transcribe(audio, path_or_hf_repo=MODEL, word_timestamps=True, language="en",
                                  condition_on_previous_text=False, initial_prompt=prompt, verbose=None)


def vocabulary(call):
    """The names a deployment would hand its transcriber from the CRM and the calendar invite: the seller, the
    account when it has a name, the competitor on file, and the people on the call. Anyone the call only mentions
    stays out, since nothing would know them beforehand."""
    cast = json.loads(HERE.joinpath("calls", "cast.json").read_text(encoding="utf-8"))
    spec = json.loads(HERE.joinpath("calls", "specs", f"{call}.json").read_text(encoding="utf-8"))
    people = cast["deal"] if spec["kind"] == "deal" else spec["cast"]
    names = [cast["seller"]] + ([cast["buyer"]] if spec["kind"] == "deal" else []) + [cast["competitor"]]
    names += [people[c]["name"] for c in spec["speakers"] if c in people]
    return ", ".join(names) + "."


def chunks(stretches, join=0.8):
    """Stretches closer than 0.8 seconds become one chunk, so Whisper hears whole sentences, not fragments."""
    out = []
    for s, e in stretches:
        if out and s - out[-1][1] < join:
            out[-1][1] = e
        else:
            out.append([s, e])
    return out


def words_in(audio, stretches, prompt=None):
    """Transcribe only the stretches, and put every word back on the call's clock."""
    out, total = [], len(audio) / SR
    for start, end in chunks(stretches):
        a, b = max(0.0, start - PAD), min(total, end + PAD)
        chunk = audio[int(a * SR):int(b * SR)]
        if len(chunk) < int(0.2 * SR):
            continue
        for seg in transcribe(chunk, prompt).get("segments", []):
            for w in seg.get("words", []):
                out.append({"w": w["word"].strip(), "start": round(a + w["start"], 3),
                            "end": round(a + w["end"], 3), "p": w.get("probability")})
    return out


def warmup():
    path = HERE.joinpath("owner", "out", "warmup.wav")
    if not path.exists():
        raise SystemExit("owner/out/warmup.wav is missing. The voice warm-up runs first in bootstrap.")
    text = transcribe(load16k(path)).get("text", "").strip()
    print(f"Transcription model ready. It heard: {text}")


def run_call(call):
    raw = HERE.joinpath("data", "raw", call)
    vad = json.loads(HERE.joinpath("data", "vad", f"{call}.json").read_text(encoding="utf-8"))
    prompt = vocabulary(call)
    result = {"call": call, "tool": "mlx-whisper", "model": MODEL, "date": date.today().isoformat(),
              "pad_s": PAD, "vocabulary": prompt, "tracks": {}, "clean_tracks": {}}
    missing = 0
    for speaker, stretches in vad["tracks"].items():
        words = words_in(load16k(raw.joinpath(f"{speaker}.wav")), stretches, prompt)
        missing += sum(1 for w in words if w["p"] is None)
        result["tracks"][speaker] = words
        clean = raw.joinpath(f"{speaker}.clean.wav")
        if clean.exists():
            result["clean_tracks"][speaker] = words_in(load16k(clean), stretches, prompt)
    if missing:
        raise SystemExit(f"{call}: {missing} words came back without a probability. Switch this step to "
                         "whisper.cpp.")
    out = HERE.joinpath("data", "transcripts", f"{call}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    n = sum(len(v) for v in result["tracks"].values())
    print(f"  {call}: {n} words across {len(result['tracks'])} tracks")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--warmup", action="store_true")
    ap.add_argument("--calls", default="")
    a = ap.parse_args(argv)
    if a.warmup:
        return warmup()
    names = [c for c in a.calls.split(",") if c]
    calls = names or sorted(p.stem for p in HERE.joinpath("data", "vad").glob("*.json"))
    if not calls:
        raise SystemExit("No VAD files in data/vad/. Run bash owner/make_audio.sh first, which finds the speech on "
                         "each track.")
    print(f"Transcribing {len(calls)} calls with {MODEL}")
    for call in calls:
        run_call(call)


if __name__ == "__main__":
    sys.exit(main())
