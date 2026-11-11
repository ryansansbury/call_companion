"""The owner's machine only. Record the three AI steps the page replays.

    bash owner/record_ai_runs.sh --split dev                    the development round, before the prompts freeze
    bash owner/record_ai_runs.sh --split test                   the scored round, after the freeze
    bash owner/record_ai_runs.sh --split deal                   the three deal calls the page shows first
    bash owner/record_ai_runs.sh --split dev --models compare   every model in config/models.json's compare list
    bash owner/record_ai_runs.sh --split all --stand-in         a dry run with no model and no network

For each call and model it runs A1 (extract), then A2 (the follow-up, from A1's checked facts only) and A3 (the
coaching note). Every reply is validated, and a reply that isn't valid JSON in the schema gets one repair request.
A follow-up that makes an unsupported claim is kept as it is, since catching that is the point. Each record goes to
data/ai_runs/<step>/<call>/<model>.json with the prompt hash, the input hash, the reply, the validation, tokens, cost
and time, and each call adds a line to data/ai_runs/audit.jsonl. A record that already matches today's prompt and
input is skipped, so a stopped run can simply start again. Test and deal runs need the prompts frozen first.
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from agents import inputs, llm, validate  # noqa: E402
from engine import coaching, segments  # noqa: E402

RUNS = HERE.joinpath("data", "ai_runs")


def key_for(service):
    done = subprocess.run(["security", "find-generic-password", "-s", service, "-w"], capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit(f"No key saved as {service}. Run: bash owner/keys.sh openai --from policy-reconciler-openai")
    return done.stdout.strip()


def config():
    return json.loads(HERE.joinpath("config", "models.json").read_text(encoding="utf-8"))


def calls_in(split):
    specs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(HERE.joinpath("calls", "specs").glob("*.json"))]
    return [s["id"] for s in specs if split == "all" or s["split"] == split]


def load_segments(call, dev):
    folder = "dev_transcripts" if dev else "transcripts"
    path = HERE.joinpath("data", folder, f"{call}.json")
    if not path.exists():
        raise SystemExit(f"{call}: no {folder}/{call}.json. Run owner/transcribe.sh first.")
    transcript = json.loads(path.read_text(encoding="utf-8"))
    return transcript, segments.from_transcript(transcript)


def frozen_ok(stage="prompts"):
    """True when evals/frozen.json holds the stage and nothing in it has changed since."""
    from evals import freeze
    return freeze.ready(stage)


def record_path(step, call, model):
    return RUNS.joinpath(step, call, f"{model}.json")


def already(step, call, model, input_hash):
    path = record_path(step, call, model)
    if not path.exists():
        return None
    rec = json.loads(path.read_text(encoding="utf-8"))
    if rec.get("prompt_hash") == inputs.prompt_hash(step.split("-")[0]) and rec.get("input_hash") == input_hash:
        return rec
    return None


def audit(line):
    RUNS.mkdir(parents=True, exist_ok=True)
    with RUNS.joinpath("audit.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")


def run_step(backend, label, step, call, model, system, payload, check):
    """Call the model, validate, send one repair request if the reply's shape is wrong, and save the record."""
    user = json.dumps(payload, ensure_ascii=False)
    input_hash = inputs.digest(payload)
    done = already(step, call, model, input_hash)
    if done:
        return done, True
    t0 = time.time()
    text, meta = backend(system, user)
    result, held, problems = check(text)
    repaired = False
    if problems:
        fix = (user + "\n\nYour reply had these problems:\n- " + "\n- ".join(problems) +
               "\n\nReturn the complete corrected JSON, and nothing else.")
        text2, meta2 = backend(system, fix)
        result2, held2, problems2 = check(text2)
        if len(problems2) < len(problems):
            text, meta, result, held, problems, repaired = text2, meta2, result2, held2, problems2, True
    rec = {"step": step, "call": call, "model": model, "label": label, "date": date.today().isoformat(),
           "recorded_at": datetime.now().isoformat(timespec="seconds"),
           "prompt_hash": inputs.prompt_hash(step.split("-")[0]), "input_hash": input_hash, "input": payload,
           "reply": text, "repaired": repaired, "problems": problems, "held": len(held),
           "kept": len(result) if isinstance(result, list) else None,
           "ms": round((time.time() - t0) * 1000), "meta": meta}
    path = record_path(step, call, model)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    audit({"at": rec["recorded_at"], "step": step, "call": call, "model": model, "ms": rec["ms"],
           "tokens_in": (meta or {}).get("input_tokens"), "tokens_out": (meta or {}).get("output_tokens"),
           "cost_usd": (meta or {}).get("cost_usd"), "repaired": repaired, "problems": len(problems)})
    return rec, False


def sides_of(call):
    return {p["code"]: p["side"] for p in inputs.people(inputs.spec(call))}


def coaching_metrics(call, transcript, segs, dev):
    vad = HERE.joinpath("data", "vad", f"{call}.json")
    tracks = json.loads(vad.read_text(encoding="utf-8"))["tracks"] if vad.exists() and not dev \
        else coaching.stretches_from_words(transcript)
    length = max(e for rs in tracks.values() for _, e in rs)
    m = coaching.metrics(tracks, segs, sides_of(call), length)
    m.pop("asked", None)
    return m


def record_call(call, model_id, entry, steps, stand_in, dev):
    transcript, segs = load_segments(call, dev)
    s = inputs.spec(call)
    if stand_in:
        from owner import stand_in as fake
        backend = fake.Backend(call, segs)
        label = "Stand-in (no model)"
    else:
        backend = llm.backend_for(entry, key_for)
        label = entry["label"]
    lines = []
    ext = None
    if "extract" in steps or "followup" in steps:
        ext, cached = run_step(backend, label, "extract", call, model_id, inputs.prompt("extract"),
                               inputs.extract_input(call, segs), lambda t: validate.extract(t, segs))
        kept, held, problems = validate.extract(ext["reply"], segs)
        lines.append(f"A1 {len(kept)} kept, {len(held)} held{' (cached)' if cached else ''}")
    if "followup" in steps and ext:
        kept, _, _ = validate.extract(ext["reply"], segs)
        facts = validate.checker_facts(kept, segs, s["date"])
        tbl = validate.checker_table(facts, segs, s)
        variants = [("followup", ())]
        concessions = tuple(f["id"] for f in facts if f.get("kind") == "concession")
        if concessions:
            variants.append(("followup-approved", concessions))
        for step, approved in variants:
            payload = inputs.followup_input(call, facts, approved)
            rec, cached = run_step(backend, label, step, call, model_id, inputs.prompt("followup"), payload,
                                   lambda t, a=approved: validate.followup(t, tbl, a))
            _, flagged, _ = validate.followup(rec["reply"], tbl, approved)
            lines.append(f"{'A2' if step == 'followup' else 'A2 approved'} {len(flagged)} flagged claims"
                         f"{' (cached)' if cached else ''}")
    if "coach" in steps:
        reps = [p["code"] for p in inputs.people(s) if p["side"] == "seller"]
        payload = inputs.coach_input(call, segs, coaching_metrics(call, transcript, segs, dev), reps[0])
        rec, cached = run_step(backend, label, "coach", call, model_id, inputs.prompt("coach"), payload,
                               lambda t: validate.coach(t, segs))
        lines.append(f"A3 {'ok' if not rec['problems'] else 'problems'}{' (cached)' if cached else ''}")
    print(f"  {call} {model_id}: " + ", ".join(lines))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", required=True, choices=["dev", "test", "deal", "all"])
    ap.add_argument("--models", default="default", help="default, compare, or a model id")
    ap.add_argument("--steps", default="extract,followup,coach")
    ap.add_argument("--calls", default="")
    ap.add_argument("--stand-in", action="store_true")
    ap.add_argument("--dev-transcripts", action="store_true", help="development only, with --stand-in")
    a = ap.parse_args(argv)
    if a.dev_transcripts and not a.stand_in:
        raise SystemExit("--dev-transcripts only goes with --stand-in.")
    if not a.stand_in and not (frozen_ok("key") and frozen_ok("aligned")):
        raise SystemExit("The key and the aligned key have to be frozen, unchanged, before any model run. "
                         "Run: python3 evals/freeze.py --check")
    if a.split in ("test", "deal", "all") and not a.stand_in and not frozen_ok("prompts"):
        raise SystemExit("The prompts aren't frozen yet. They freeze after the dev round.")
    cfg = config()
    by_id = {m["id"]: m for m in cfg["models"]}
    if a.stand_in:
        models = [("stand-in", None)]
    else:
        ids = cfg["compare"] if a.models == "compare" else [cfg["default"]] if a.models == "default" else [a.models]
        models = [(i, by_id[i]) for i in ids if by_id[i].get("enabled", True)]
    steps = set(a.steps.split(","))
    names = [c for c in a.calls.split(",") if c] or calls_in(a.split)
    print(f"Recording {', '.join(sorted(steps))} for {len(names)} calls with {', '.join(m for m, _ in models)}")
    for model_id, entry in models:
        for call in names:
            record_call(call, model_id, entry, steps, a.stand_in, a.dev_transcripts)


if __name__ == "__main__":
    main()
