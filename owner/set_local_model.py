"""Point config/models.json's local entry at the model Ollama serves, and switch it on.

    python3 owner/set_local_model.py qwen3:14b      (owner/run_local.sh runs this)
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 1:
        raise SystemExit("Give the model name exactly as ollama list shows it.")
    name = argv[0]
    path = HERE.joinpath("config", "models.json")
    cfg = json.loads(path.read_text(encoding="utf-8"))
    for m in cfg["models"]:
        if m["id"] == "local":
            m.update(model=name, enabled=True, label=f"Local model ({name})")
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(f"config/models.json now runs {name} as the local model")


if __name__ == "__main__":
    main()
