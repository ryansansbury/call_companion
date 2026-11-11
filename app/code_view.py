"""The code section on How it works: the project's real source, copied into the page on every build.

An allowlist picks the folders. The planning files, the references, the recordings, the transcripts and the
writing-rules tool never go in, and the never-word scan reads the code with the rest of the page. The files go to
site/code.js as data apart from the page's script, and the page loads that file only when the code view opens.
Adapted from the Policy Reconciler's code view.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
FOLDERS = ("engine", "agents", "prompts", "app", "generate", "audio", "transcribe", "evals", "owner", "config",
           "tests", "calls")
TOP = ("build.py", "WORDS.md", "site/claims.js", "site/app.js", "site/app.css")
SUFFIXES = (".py", ".js", ".css", ".md", ".sh", ".json")
SKIP = ("owner/out/", "evals/frozen.json", "evals/claim_results.json", "evals/dev_scores.json", "tests/vectors/")
DEFAULT = "engine/claims.py"
FEATURED = ("engine/claims.py", "engine/evidence.py", "engine/crm.py", "engine/coaching.py", "evals/score.py")


def collect(root=HERE):
    """{path: text} for every file the code section shows."""
    root = Path(root)
    paths = [root.joinpath(t) for t in TOP]
    for folder in FOLDERS:
        if root.joinpath(folder).exists():
            paths += sorted(root.joinpath(folder).rglob("*"))
    files = {}
    for p in paths:
        rel = p.relative_to(root).as_posix()
        if p.is_file() and p.suffix in SUFFIXES and "__pycache__" not in rel and not rel.startswith(SKIP):
            files[rel] = p.read_text(encoding="utf-8")
    return files


def write(files, path=None):
    path = Path(path or HERE.joinpath("site", "code.js"))
    path.write_text("window.CCCODE = " + json.dumps({"files": files, "default": DEFAULT},
                                                     ensure_ascii=False, separators=(",", ":")) + ";\n",
                    encoding="utf-8")
    return path.stat().st_size
