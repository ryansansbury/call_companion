"""The page's data: every call, each model's validated results, the CRM records, the coaching numbers and the scores.

It's written to site/data.js as window.CC, and the page reads nothing else. A development preview builds from the
development transcripts and the stand-in, and the page labels it in red. The real build reads the transcripts, the
recorded runs and the scores, and refuses anything that isn't frozen. Each fact carries its evidence as segment ids
and quotes, plus the lowest confidence the transcriber gave a number or a name in those quotes, which the page's
cutoff compares against.
"""
import json
import math
import re
from pathlib import Path

from agents import inputs, replay
from engine import claims, coaching, crm, diff, peaks, segments
from engine.align import canon

HERE = Path(__file__).resolve().parent.parent
DEAL = ["deal-1", "deal-2", "deal-3"]
PREVIEW_MODEL = "stand-in"


def specs():
    out = [json.loads(p.read_text(encoding="utf-8")) for p in HERE.joinpath("calls", "specs").glob("*.json")]
    return sorted(out, key=lambda s: (s["kind"] != "deal", s["id"]))


def load_transcript(call, dev):
    folder = "dev_transcripts" if dev else "transcripts"
    path = HERE.joinpath("data", folder, f"{call}.json")
    if not path.exists():
        raise SystemExit(f"{call}: no data/{folder}/{call}.json. "
                         + ("Run python3 generate/dev_transcript.py." if dev else "Run owner/transcribe.sh first."))
    return json.loads(path.read_text(encoding="utf-8"))


RISKY = re.compile(r"\d|^(?:" + "|".join(sorted(claims.NUMBER_WORDS)) + r")$")


def confidence(evidence, by_id):
    """The lowest confidence on a number or a name inside the quoted words. 1.0 when the quotes hold neither."""
    low = 1.0
    for seg_id, quote in evidence:
        seg = by_id.get(seg_id)
        if not seg:
            continue
        words = seg["words"]
        flat = [canon(w["w"]) for w in words]
        want = canon(quote).split()
        start = next((i for i in range(len(flat) - len(want) + 1)
                      if " ".join(flat[i:i + len(want)]).split() == want), None) if want else None
        span = words[start:start + len(want)] if start is not None else words
        for j, w in enumerate(span):
            text = w["w"].strip(".,?!\"'")
            name = text[:1].isupper() and text not in ("I", "I'm", "I'll", "I'd") and (start or 0) + j > 0
            if (RISKY.search(canon(text)) or name) and w.get("p") is not None:
                low = min(low, float(w["p"]))
    return round(low, 3)


def page_fact(item, by_id, checked):
    ev = [[e["segment"], e["quote"]] for e in item.get("evidence") or [] if e.get("segment") in by_id]
    out = {"id": item["id"], "field": item["field"], "value": item["value"], "ev": ev,
           "conf": confidence(ev, by_id)}
    for k in ("number", "unit", "due", "owner", "name", "role", "kind", "by", "who"):
        if item.get(k) not in (None, ""):
            out[k] = item[k]
    if checked.get("date"):
        out["date"] = checked["date"]
    return out


def crm_facts(view):
    by = {k["id"]: k for k in view["kept"]}
    out = []
    for f in view["facts"]:
        k = by.get(f["id"], {})
        out.append(dict(f, owner=k.get("owner"), name=k.get("name"), role=k.get("role"), by=k.get("by"),
                        who=k.get("who")))
    return out


def slim_record(rec):
    """The record with list fields as fact ids, which the page looks up in the call's facts."""
    fields = {}
    for key, v in rec["fields"].items():
        if isinstance(v, list) and key != "stakeholders":
            fields[key] = [[x["fact"], x["call"], x.get("first_call")] for x in v]
        else:
            fields[key] = v
    return {"stage": rec["stage"], "checks": [[c["id"], c["met"], c["fact"], c["call"]] for c in rec["checks"]],
            "fields": fields, "payload": crm.payload(rec)}


def said_at(item, by_id):
    """The second a fact's first quote has been said, read from where the quote ends in its segment. The page's replay
    uses the same rule (factAt in site/app.js), so a stage move cites the fact the replay steps on."""
    ev = [e for e in (item or {}).get("evidence") or [] if e.get("segment") in by_id]
    if not ev:
        return None
    g, quote = by_id[ev[0]["segment"]], ev[0].get("quote") or ""
    at = g["text"].find(quote) if quote else -1
    end = (at + len(quote)) / max(1, len(g["text"])) if at >= 0 else 1.0
    return g["start"] + (g["end"] - g["start"]) * min(1.0, end)


def crm_for(model, views, roster_by_call, dates, seg_cache=None):
    """{call: {record, approved, changes}} for one model, the deal built across its calls."""
    out = {}
    cfg = crm.load()
    by_call = {call: {g["id"]: g for g in segs} for call, (_, segs) in (seg_cache or {}).items()}

    def when(fact_id, call):
        f = next((x for x in (views.get(call) or {}).get("facts", []) if x["id"] == fact_id), None)
        return said_at(f, by_call.get(call, {}))
    deal_calls = [(c, crm_facts(views[c])) for c in DEAL if views.get(c)]
    if deal_calls:
        roster = roster_by_call[DEAL[0]]
        concessions = [i for c in DEAL if views.get(c) for i in views[c]["concessions"]]
        plain = crm.deal(deal_calls, cfg, (), roster)
        approved = crm.deal(deal_calls, cfg, concessions, roster) if concessions else None
        for i, (call, _) in enumerate(deal_calls):
            prev = plain[i - 1] if i else None
            out[call] = {"record": slim_record(plain[i]),
                         "approved": slim_record(approved[i]) if approved else None,
                         "changes": diff.changes(prev, plain[i], dates[call], cfg, when if by_call else None),
                         "concessions": concessions}
    for call, view in views.items():
        if call in DEAL or not view:
            continue
        facts = crm_facts(view)
        rec = crm.record([dict(f, call=call) for f in facts], cfg, (), roster_by_call[call], call)
        appr = crm.record([dict(f, call=call) for f in facts], cfg, view["concessions"], roster_by_call[call], call) \
            if view["concessions"] else None
        out[call] = {"record": slim_record(rec), "approved": slim_record(appr) if appr else None, "changes": None,
                     "concessions": view["concessions"]}
    return out


def synth_peaks(transcript, length):
    """Lanes for a preview, from the development transcript's word times. Labeled preview on the page."""
    n = int(math.ceil(length * peaks.RATE_PER_S)) + 1
    out = {}
    for code, words in transcript["tracks"].items():
        levels = [0.0] * n
        for i, w in enumerate(words):
            a, b = int(w["start"] * peaks.RATE_PER_S), int(w["end"] * peaks.RATE_PER_S) + 1
            for k in range(a, min(b, n)):
                levels[k] = max(levels[k], 0.35 + 0.6 * abs(math.sin(i * 1.7 + k * 0.9)))
        out[code] = peaks.encode(levels, 1.0)
    return out


def lanes(call, transcript, length, dev):
    path = HERE.joinpath("data", "peaks", f"{call}.json")
    if not dev and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["tracks"]
    if not dev:
        raise SystemExit(f"{call}: no data/peaks/{call}.json. Run owner/make_audio.sh first.")
    return synth_peaks(transcript, length)


def coach_numbers(call, transcript, segs, dev):
    vad = HERE.joinpath("data", "vad", f"{call}.json")
    if dev:
        tracks = coaching.stretches_from_words(transcript)
    else:
        if not vad.exists():
            raise SystemExit(f"{call}: no data/vad/{call}.json. Run owner/make_audio.sh first.")
        tracks = json.loads(vad.read_text(encoding="utf-8"))["tracks"]
    sides = {p["code"]: p["side"] for p in inputs.people(inputs.spec(call))}
    length = max(e for rs in tracks.values() for _, e in rs)
    m = coaching.metrics(tracks, segs, sides, length)
    asked = m.pop("asked", [])
    sc = coaching.score(m, coaching.load_rubric())
    return {"metrics": m, "parts": {k: v["score"] for k, v in sc["parts"].items()}, "score": sc["score"],
            "asked": asked}


def next_step_quality(view):
    steps = [f for f in view["facts"] if f["field"] == "next_steps"]
    kept = {k["id"]: k for k in view["kept"]}
    good = [f for f in steps if f.get("date") and (kept.get(f["id"], {}).get("owner") or
                                                   re.match(r"[A-Z][a-z]+ ", f["value"]))]
    return [len(good), len(steps)]


def samples_for(call, tbl, planted, cfg):
    """The Email tab's sample bad claims for this call, each confirmed to be flagged."""
    picks = cfg["pick"].get(call, {})
    mine = [p for p in planted if p["call"] == call]
    out = {}
    for kind, generic in cfg["generic"].items():
        pid = picks.get(kind)
        own = next((p for p in mine if p["id"] == pid), None) or next((p for p in mine if p["type"] == kind), None)
        for sentence in ([own["sentence"]] if own else []) + [generic]:
            result = claims.check_email(sentence, tbl)
            if any(c["status"] != "supported" for s in result for c in s["claims"]):
                out[kind] = sentence
                break
    return out


def runs_table(models):
    out = []
    for model in models:
        for step in replay.STEPS:
            recs = [json.loads(p.read_text(encoding="utf-8"))
                    for p in HERE.joinpath("data", "ai_runs", step).glob(f"*/{model}.json")]
            if recs:
                days = sorted(r["date"] for r in recs)
                out.append({"model": model, "label": recs[0].get("label"), "step": step, "calls": len(recs),
                            "first": days[0], "last": days[-1]})
    return out


def read_json(*parts):
    path = HERE.joinpath(*parts)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def build(w, dev=False):
    from evals import compare
    cfg_models = compare.config()
    labels = {m["id"]: m["label"] for m in cfg_models["models"]}
    labels[PREVIEW_MODEL] = "Stand-in (no model)"
    models = [PREVIEW_MODEL] if dev else [m for m in replay.models() if m != PREVIEW_MODEL]
    planted = read_json("evals", "planted_claims.json")["claims"]
    sample_cfg = read_json("calls", "samples.json")
    all_specs = specs()
    calls, views, rosters, dates = [], {m: {} for m in models}, {}, {}
    seg_cache = {}
    for s in all_specs:
        call = s["id"]
        transcript = load_transcript(call, dev)
        segs = segments.from_transcript(transcript)
        seg_cache[call] = (transcript, segs)
        rosters[call] = inputs.roster(s)
        dates[call] = s["date"]
        for m in models:
            views[m][call] = replay.view(call, m, segs, strict=not dev)
    scores = read_json("evals", "dev_scores.json" if dev else "scores.json") or {"models": {}}
    comparison = compare.compare(views, scores["models"], cfg_models)
    if not dev:
        HERE.joinpath("evals", "model_comparison.json").write_text(json.dumps(comparison, indent=1) + "\n",
                                                                   encoding="utf-8")
    route = comparison["route"] or (models[0] if models else None)
    order = [route] + [m for m in models if m != route] if route else models
    crm_by_model = {m: crm_for(m, views[m], rosters, dates, seg_cache) for m in models}
    for s in all_specs:
        call = s["id"]
        transcript, segs = seg_cache[call]
        by_id = {g["id"]: g for g in segs}
        length = max([g["end"] for g in segs] + [0]) + 1.0
        audio = HERE.joinpath("site", "audio", f"{call}.v1.m4a")
        people = inputs.people(s)
        rep = next(p["code"] for p in people if p["side"] == "seller")
        coach = coach_numbers(call, transcript, segs, dev)
        ai = {}
        for m in models:
            v = views[m].get(call)
            if not v:
                continue
            checked = {f["id"]: f for f in v["facts"]}
            ai[m] = {"facts": [page_fact(k, by_id, checked.get(k["id"], {})) for k in v["kept"]],
                     "held": [{"id": h["id"], "field": h["field"], "value": h["value"], "reasons": h["reasons"]}
                              for h in v["held"]],
                     "email": v["email"], "emailApproved": v.get("email_approved"),
                     "concessions": v["concessions"], "coach": v["coach"], "steps": next_step_quality(v),
                     "cost": round(v["cost_usd"], 5), "ms": v["ms"], "dates": v["dates"],
                     "crm": crm_by_model[m].get(call)}
        main = views.get(route, {}).get(call)
        samples = samples_for(call, main["table"], planted, sample_cfg) if main else {}
        calls.append({
            "id": call, "kind": s["kind"], "split": s["split"], "title": s["title"], "date": s["date"],
            "length": round(length, 1), "audio": f"audio/{call}.v1.m4a" if audio.exists() and not dev else None,
            "people": people, "rep": rep, "peaks": lanes(call, transcript, length, dev),
            "segs": [{"id": g["id"], "sp": g["speaker"], "s": g["start"], "e": g["end"], "text": g["text"],
                      "w": [[x["w"], round(x["p"], 2) if x.get("p") is not None else None] for x in g["words"]]}
                     for g in segs],
            "coach": coach, "ai": ai, "samples": samples, "roster": rosters[call], "companies": inputs.companies(s),
        })
    results = {
        "scores": {m: {s: slim_score(v) for s, v in sc.items()} for m, sc in scores["models"].items()}, "claims": summarize_claims(read_json("evals", "claim_results.json")),
        "wer": None if dev else read_json("evals", "wer.json"), "timing": None if dev else read_json("evals", "timing.json"),
        "comparison": comparison, "runs": runs_table(order), "misses": misses(scores["models"].get(route), dev),
        "questions": {k: v for k, v in (read_json("evals", "questions.json") or {}).items() if k != "disagreements"},
    }
    return {
        "v": 1, "preview": dev, "ui": w.ui(), "lexicon": claims.lexicon(), "rubric": coaching.load_rubric(),
        "crm": {"stages": crm.load()["stages"], "fields": crm.load()["fields"], "object": crm.load()["object"]},
        "models": [{"id": m, "label": labels.get(m, m), "local": m == "local"} for m in order],
        "route": route, "deal": DEAL, "calls": calls, "results": results,
    }


def slim_score(v):
    if not v:
        return None
    return {k: v[k] for k in ("f1", "precision", "recall", "tp", "fp", "fn", "unsupported_rate", "not_found",
                              "fields")}


def summarize_claims(r):
    if not r:
        return None
    keep = ("planted", "caught", "right_status", "catch_rate", "by_type", "clean_emails", "clean_claims",
            "false_alarm_emails", "false_alarm_rate", "bars", "passes")
    out = {k: r[k] for k in keep}
    out["missed"] = [{"id": x["id"], "call": x["call"], "type": x["type"], "sentence": x["sentence"]}
                     for x in r["rows"] if not x["caught"]]
    return out


def misses(model_scores, dev):
    """The key facts the routed model missed on the test calls, with their values."""
    if not model_scores or not model_scores.get("test"):
        return []
    out = []
    for call, c in sorted(model_scores["test"]["calls"].items()):
        key = read_json("data", "dev_key" if dev else "key", f"{call}.json")
        items = {x["id"]: x for x in key["facts"] + key["commitments"]}
        for fid in c["missed"]:
            x = items[fid]
            out.append({"call": call, "id": fid, "field": x["field"], "value": x["value"]})
    return out


def write(data, path=None):
    path = Path(path or HERE.joinpath("site", "data.js"))
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    path.write_text("window.CC = " + body + ";\n", encoding="utf-8")
    return path.stat().st_size
