"""Words that must never ship, and the scan that enforces it.

The list comes from tools/lint_copy.py's NEVER tuple and reference/private_words.txt (a line written rot13:... is
decoded first). Neither file ships, and both are optional, so the public copy still builds without them. A match is a
whole word or phrase without regard to case, so "cat" never matches "category." Adapted from the Policy Reconciler.
"""
import codecs
import importlib.util
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def words(private=None, tool=None):
    out = []
    private = Path(private or HERE.joinpath("reference", "private_words.txt"))
    if private.exists():
        for line in private.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(codecs.decode(line[6:], "rot13").lower() if line.startswith("rot13:") else line.lower())
    tool = Path(tool or HERE.joinpath("tools", "lint_copy.py"))
    if tool.exists():
        spec = importlib.util.spec_from_file_location("lint_copy_never", str(tool))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out += [w.lower() for w in getattr(mod, "NEVER", ())]
    return tuple(dict.fromkeys(out))


def pattern(word_list):
    parts = [r"\b" + re.escape(w).replace(r"\ ", r"\s+") + r"\b" for w in word_list]
    return re.compile("|".join(parts), re.IGNORECASE) if parts else None


def hits(text, word_list=None):
    """Every never-word found in the text, lowercased, in order of first appearance."""
    pat = pattern(word_list if word_list is not None else words())
    if not pat:
        return []
    return list(dict.fromkeys(m.group(0).lower() for m in pat.finditer(text)))
