"""Read a call script: one turn per line, with an id, a speaker, optional marks in braces, and the words.

    d1-012  OPS   {pause 0.4} A reefer unit died overnight and nobody knew until load-out.

The marks:
- {pause s} is the gap before the line;
- {overlap s} starts the line that many seconds before the previous line ends;
- {cut n} means the next speaker cuts in after this line's nth word, and the mixer fades this line out;
- {bc s} makes the line a backchannel on its speaker's track, s seconds into the previous line, which doesn't move
  the call's clock.

Lines that don't start with an id (headings, notes, blank lines) are ignored, so the file reads like a script.
Standard library only, since the build and the owner's voice script both use it.
"""
import re
from pathlib import Path

LINE = re.compile(r"^([a-z0-9]+-\d{3})\s+([A-Z][A-Z0-9]*)\s+(.*\S)\s*$")
MARK = re.compile(r"^\{(pause|overlap|cut|bc)\s+([0-9.]+)\}\s*")
WORD = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)?(?:[.,][0-9]+)?")


def words(text):
    """The words of a line, the way the validator and the cut mark count them."""
    return WORD.findall(text)


def parse(text):
    """Every turn in order, as {id, speaker, text, marks, words, source_line}."""
    turns = []
    for n, raw in enumerate(text.splitlines(), 1):
        m = LINE.match(raw)
        if not m:
            continue
        lid, speaker, rest = m.groups()
        marks = {}
        while True:
            mm = MARK.match(rest)
            if not mm:
                break
            marks[mm.group(1)] = float(mm.group(2))
            rest = rest[mm.end():]
        if "cut" in marks:
            marks["cut"] = int(marks["cut"])
        rest = rest.strip()
        turns.append({"id": lid, "speaker": speaker, "text": rest, "marks": marks, "words": words(rest),
                      "source_line": n})
    return turns


def load(path):
    return parse(Path(path).read_text(encoding="utf-8"))
