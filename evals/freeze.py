"""Freeze the key, then the aligned key, then the prompts and the matchers, so nothing scored is tuned after the fact.

    python3 evals/freeze.py key         at G3: specs, scripts, cast, planted claims, clean emails, policy, rubric, CRM
    python3 evals/freeze.py aligned     after the transcripts: the aligned key in data/key/
    python3 evals/freeze.py prompts     after the dev runs: the three prompts and the code that scores
    python3 evals/freeze.py --check     list anything changed since it was frozen, and exit 1 if so

Each stage writes its hashes into evals/frozen.json once. Freezing a stage again needs --again, and the old hashes
move to "history" with the time, so a change after the fact shows. The recorder refuses real model runs until the key
and the aligned key are frozen, and test and deal runs until the prompts are. build.py runs the check before it shows
any score. Standard library only.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

FROZEN = HERE.joinpath("evals", "frozen.json")
STAGES = {
    "key": ["calls/specs/*.json", "calls/scripts/*.md", "calls/cast.json", "evals/planted_claims.json",
            "evals/clean_emails.json", "config/policy.json", "config/rubric.json", "config/crm.json"],
    "aligned": ["data/key/*.json"],
    "matchers": ["evals/score.py", "evals/key.py", "engine/claims.py", "engine/evidence.py", "engine/numerals.py",
                 "engine/dates.py", "agents/validate.py"],
}
STEPS = ("extract", "followup", "coach")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def files(stage):
    out = {}
    for pattern in STAGES[stage]:
        for p in sorted(HERE.glob(pattern)):
            out[p.relative_to(HERE).as_posix()] = sha(p)
    return out


def prompt_hashes():
    from agents import inputs
    return {s: inputs.prompt_hash(s) for s in STEPS}


def load():
    return json.loads(FROZEN.read_text(encoding="utf-8")) if FROZEN.exists() else {}


def now():
    return datetime.now(ZoneInfo("America/Los_Angeles")).isoformat(timespec="seconds")


def current(stage):
    if stage == "prompts":
        return {"prompts": prompt_hashes(), "matchers": files("matchers")}
    return {stage: files(stage)}


def freeze(stage, again=False):
    data = load()
    keys = ["prompts", "matchers"] if stage == "prompts" else [stage]
    if any(k in data for k in keys) and not again:
        raise SystemExit(f"{stage} is already frozen at {data.get('at', {}).get(stage)}. Use --again to refreeze, "
                         f"and the old hashes go to history.")
    if stage == "aligned" and not files("aligned"):
        raise SystemExit("data/key/ is empty. Run engine/align.py first.")
    if stage == "key" and not files("key"):
        raise SystemExit("Nothing to freeze.")
    if any(k in data for k in keys):
        data.setdefault("history", []).append({"stage": stage, "at": data.get("at", {}).get(stage),
                                               "replaced": now(), **{k: data[k] for k in keys}})
    data.update(current(stage))
    data.setdefault("at", {})[stage] = now()
    FROZEN.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return data


def changed(stage):
    """What differs from the frozen hashes for a stage: (path or step, why). None when the stage isn't frozen."""
    data = load()
    keys = ["prompts", "matchers"] if stage == "prompts" else [stage]
    if not all(k in data for k in keys):
        return None
    out = []
    for k, now_hashes in current(stage).items():
        then = data[k]
        for name in sorted(set(then) | set(now_hashes)):
            if name not in now_hashes:
                out.append((name, "removed"))
            elif name not in then:
                out.append((name, "added"))
            elif then[name] != now_hashes[name]:
                out.append((name, "changed"))
    return out


def ready(stage):
    """True when the stage is frozen and nothing in it has changed."""
    c = changed(stage)
    return c is not None and not c


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("stage", nargs="?", choices=["key", "aligned", "prompts"])
    ap.add_argument("--again", action="store_true", help="refreeze a stage, keeping the old hashes in history")
    ap.add_argument("--check", action="store_true", help="list changes since each stage was frozen")
    a = ap.parse_args(argv)
    if a.check or not a.stage:
        bad = False
        for stage in ("key", "aligned", "prompts"):
            c = changed(stage)
            if c is None:
                print(f"{stage}: not frozen yet")
                continue
            print(f"{stage}: frozen {load()['at'][stage]}, {'unchanged' if not c else f'{len(c)} changed'}")
            for name, why in c:
                print(f"  {why}: {name}")
                bad = True
        return 1 if bad else 0
    data = freeze(a.stage, a.again)
    n = sum(len(v) for k, v in current(a.stage).items())
    print(f"Froze {a.stage} at {data['at'][a.stage]}: {n} hashes in evals/frozen.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
