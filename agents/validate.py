"""Check every AI reply before anything uses it, in the recorder and again in the build.

- A1 extract: the reply must be JSON in the schema, and every item must pass the evidence check. Items that fail are
  held with their reasons, never shown as facts, and counted as unsupported.
- A2 follow-up: JSON in the schema, then the claim checker on every sentence. A sentence with an unsupported claim or
  an unapproved concession is flagged with the reason.
- A3 coaching note: three strengths and three improvements, each citing a segment whose text holds the quote.

Each returns (kept, held, problems): what passed, what didn't with its reasons, and anything wrong with the reply as
a whole. The recorder sends one repair request for the problems, and the build only ever reads.
"""
import json
import re

from engine import claims, evidence

FIELDS = ["metrics", "economic_buyer", "decision_criteria", "decision_process", "paper_process", "pain", "champion",
          "competition", "critical_event", "budget", "pricing", "amount", "close_date", "next_steps", "stakeholders",
          "risks", "account", "seller_claims"]
KINDS = {"deliverable", "meeting", "decision", "concession", "terms"}


def parse(text):
    """The JSON object in a reply, tolerating a code fence or a sentence around it, and a thinking model's <think>
    block, whose braces would otherwise read as the start of the reply."""
    t = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if m:
        t = m.group(1).strip()
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in the reply")
    return json.loads(t[start:end + 1])


def extract(reply, segs):
    """Validated A1 items with stable ids (metrics-1, next_steps-2, commitments-1), plus the held ones."""
    problems, kept, held = [], [], []
    try:
        data = parse(reply)
    except (ValueError, json.JSONDecodeError) as e:
        return [], [], [f"the reply isn't valid JSON: {e}"]
    fields = data.get("fields")
    if not isinstance(fields, dict):
        return [], [], ["the reply has no fields object"]
    by_id = {g["id"]: g for g in segs}
    for name in FIELDS:
        items = fields.get(name, [])
        if not isinstance(items, list):
            problems.append(f"{name} isn't a list")
            continue
        for n, item in enumerate(items, 1):
            if not isinstance(item, dict) or not item.get("value"):
                problems.append(f"{name} item {n} has no value")
                continue
            entry = dict(item, id=f"{name}-{n}", field=name)
            why = evidence.check(item, by_id)
            (held if why else kept).append(dict(entry, reasons=why) if why else entry)
    for n, c in enumerate(data.get("commitments", []) or [], 1):
        if not isinstance(c, dict) or not c.get("what"):
            problems.append(f"commitment {n} has no what")
            continue
        entry = dict(c, id=f"commitments-{n}", field="commitments", value=c["what"])
        if c.get("kind") not in KINDS:
            entry["kind"] = "deliverable"
        why = evidence.check({"value": "", "evidence": c.get("evidence")}, by_id)
        (held if why else kept).append(dict(entry, reasons=why) if why else entry)
    unknown = sorted(set(fields) - set(FIELDS))
    if unknown:
        problems.append(f"fields the schema doesn't have: {', '.join(unknown)}")
    return kept, held, problems


def checker_facts(kept, segs, call_day):
    """The validated items in the shape the claim checker reads: quotes, and the due date resolved from the call's
    day. claims.table() finds the other dates in the value and the quotes."""
    from engine import dates
    by_id = {g["id"]: g for g in segs}
    out = []
    for item in kept:
        quotes = [e["quote"] for e in item.get("evidence") or [] if e.get("segment") in by_id]
        due = dates.resolve(item.get("due") or "", call_day)
        out.append({"id": item["id"], "field": item["field"], "value": item["value"], "number": item.get("number"),
                    "unit": item.get("unit"), "kind": item.get("kind"), "approved": item.get("kind") != "concession",
                    "date": due.isoformat() if due else None, "quotes": quotes})
    return out


def checker_table(facts, segs, s):
    """The claim checker's table for a call: its checked facts, the people and companies it can name, and the
    transcript's words."""
    from agents import inputs
    return claims.table(facts, s["date"], inputs.roster(s), inputs.companies(s), "\n".join(g["text"] for g in segs))


def followup(reply, tbl, approved=()):
    """The A2 draft with every sentence checked on its own, plus the claims flagged in it."""
    problems = []
    try:
        data = parse(reply)
    except (ValueError, json.JSONDecodeError) as e:
        return None, [], [f"the reply isn't valid JSON: {e}"]
    sents = data.get("sentences")
    if not data.get("subject") or not isinstance(sents, list) or not sents or \
            not all(isinstance(x, dict) and x.get("text") for x in sents):
        return None, [], ["the reply needs a subject and a list of sentences, each with its text"]
    t = claims.approve(tbl, approved) if approved else tbl
    known = {f["id"] for f in tbl["facts"]}
    checked = []
    for x in sents:
        claims_here, pos = [], 0
        for part in claims.check_email(x["text"], t):
            at = x["text"].find(part["sentence"], pos)
            at = at if at >= 0 else pos
            claims_here += [dict(c, start=c["start"] + at, end=c["end"] + at) for c in part["claims"]]
            pos = at + len(part["sentence"])
        cited = [i for i in x.get("facts") or [] if i in known]
        checked.append({"text": x["text"], "facts": cited, "claims": claims_here})
        stray = [i for i in x.get("facts") or [] if i not in known]
        if stray:
            problems.append(f"a sentence cites facts that don't exist: {', '.join(stray)}")
    flagged = [c for x in checked for c in x["claims"] if c["status"] != "supported"]
    return {"subject": data["subject"], "sentences": checked}, flagged, problems


def coach(reply, segs):
    problems, kept = [], {"strengths": [], "improvements": []}
    try:
        data = parse(reply)
    except (ValueError, json.JSONDecodeError) as e:
        return None, [], [f"the reply isn't valid JSON: {e}"]
    by_id = {g["id"]: g for g in segs}
    held = []
    for part in ("strengths", "improvements"):
        items = data.get(part)
        if not isinstance(items, list) or len(items) != 3:
            problems.append(f"{part} needs exactly three points")
            continue
        for item in items:
            seg = by_id.get(item.get("segment"))
            if seg and evidence.quote_in(item.get("quote"), seg["text"]):
                kept[part].append(item)
            else:
                held.append(dict(item, reasons=["the quote isn't in that segment"]))
    return kept, held, problems
