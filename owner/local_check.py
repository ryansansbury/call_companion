"""The owner's machine only. One short question to the local model before its long run.

    python3 owner/local_check.py

It goes through the same backend and settings the recorder uses. A model that doesn't answer, or still thinks with
its thinking off, stops here in seconds instead of ten minutes into the first call, and run 3 builds the page without
it. The first answer can take a minute while Ollama loads the model.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from agents import llm  # noqa: E402


def no_key(service):
    raise SystemExit(f"The local model shouldn't need a key, but its config names {service}.")


def main():
    cfg = json.loads(HERE.joinpath("config", "models.json").read_text(encoding="utf-8"))
    entry = next((m for m in cfg["models"] if m["id"] == "local"), None)
    if not entry or not entry.get("enabled"):
        sys.exit("The local model is switched off in config/models.json.")
    backend = llm.backend_for(dict(entry, timeout=300, max_tokens=200), no_key)
    t0 = time.time()
    try:
        text, meta = backend("Answer with one word.", "Is a clear daytime sky usually blue? Answer yes or no.")
    except Exception as e:  # noqa: BLE001 - any failure means the long run would fail too
        sys.exit(f"{entry['model']} didn't answer ({str(e)[:200]}). Is Ollama running with that model pulled?")
    secs = time.time() - t0
    thought = meta.get("reasoning_chars") or 0
    out = meta.get("output_tokens") or 0
    if thought or "<think>" in text or out > 40:
        sys.exit(f"{entry['model']} still thought before answering ({thought} characters of thinking and {out} tokens "
                 f"out in {secs:.0f} s), so Ollama didn't take the thinking-off setting.")
    print(f"{entry['model']} answered {text.strip()[:20]!r} in {secs:.1f} s with its thinking off.")


if __name__ == "__main__":
    main()
