"""One command builds the page from what the pipeline and the owner's runs left on disk.

    python3 build.py                  the real page, from the transcripts, the recorded runs and the frozen key
    python3 build.py --dev-preview    a development preview from the development transcripts and the stand-in,
                                      labeled in red on the page and never staged for the site

The stages: score (the claim checker's planted and clean sets, then the extraction scores), then the page (the data
bundle, the code view, index.html, the never-word scan and the weight check). No AI step runs here. The build replays
what the owner's recorder saved and validates every reply again before the page uses it.
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from app import bundle, code_view, never, page, readme, words  # noqa: E402

WEIGHT_LIMIT = 1_500_000
SHIPPED = ("index.html", "app.css", "app.js", "claims.js", "data.js")


def score_stage(dev):
    from evals import claims_eval, questions, score
    claims_eval.main()
    questions.main()
    if dev:
        score.main(["--dev-preview"])
        return
    from evals import freeze
    for stage in ("key", "aligned"):
        if not freeze.ready(stage):
            raise SystemExit(f"The {stage} stage isn't frozen and unchanged. Run python3 evals/freeze.py --check.")
    score.main([])


def page_stage(dev):
    w = words.load()
    data = bundle.build(w, dev)
    size = bundle.write(data)
    code_size = code_view.write(code_view.collect())
    html = page.render(w, data)
    page.write(html)
    readme.write(data)
    site = HERE.joinpath("site")
    word_list = never.words()
    found = {}
    for name in SHIPPED + ("code.js",):
        hits = never.hits(site.joinpath(name).read_text(encoding="utf-8"), word_list)
        if hits:
            found[name] = hits
    for name in ("WORDS.md",):
        hits = never.hits(HERE.joinpath(name).read_text(encoding="utf-8"), word_list)
        if hits:
            found[name] = hits
    if found:
        raise SystemExit("Never-words in what ships: " + "; ".join(f"{k} ({len(v)})" for k, v in found.items()))
    fonts = sum(p.stat().st_size for p in site.joinpath("fonts").glob("*.woff2"))
    weight = sum(site.joinpath(n).stat().st_size for n in SHIPPED) + fonts
    if weight > WEIGHT_LIMIT:
        raise SystemExit(f"The page weighs {weight:,} bytes without audio, over the {WEIGHT_LIMIT:,} budget.")
    missing = [k for k in w.entries if not k.startswith(("ui.", "how.", "page.")) and k not in w.used]
    return {"data": size, "code": code_size, "weight": weight, "unused": missing}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dev-preview", action="store_true")
    ap.add_argument("--only", choices=["score", "page"])
    a = ap.parse_args(argv)
    t0 = time.time()
    if a.only in (None, "score"):
        score_stage(a.dev_preview)
    if a.only in (None, "page"):
        out = page_stage(a.dev_preview)
        print(f"Page: data.js {out['data']:,} bytes, code.js {out['code']:,} bytes (loaded on demand), "
              f"{out['weight']:,} bytes without audio")
    print(f"Built {'the development preview' if a.dev_preview else 'the page'} in {time.time() - t0:.1f} s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
