"""What changed in the deal from one call's CRM record to the next, each change with the fact that caused it.

The kinds: a stage move, a new or changed amount, close date or next step, a new contact role, a new risk, any other
new fact, and a commitment kept. A meeting promised for a date counts as kept when the next call happens on that
date, since that call is the meeting. Standard library only.
"""
LABELS = {"amount": "Amount", "close_date": "Close date", "next_step": "Next step"}


def _ids(items):
    return {x["fact"] for x in items or []}


def changes(prev, cur, call_date=None, cfg=None, when=None):
    """[{kind, field, text, fact}] from prev (None before the first call) to cur.

    when(fact, call) gives the second in its call that a fact was said. With it, a stage move cites the rule met last,
    which is the one that completed the move. Without it, the move cites the first newly met rule in config order."""
    from engine import crm
    cfg = cfg or crm.load()
    labels = {f["key"]: f["label"] for f in cfg["fields"]}
    out = []
    if prev is None or prev["stage"] != cur["stage"]:
        names = [s["name"] for s in cfg["stages"]]
        was = names.index(prev["stage"]) if prev else 0
        now = names.index(cur["stage"])
        before = {c["id"]: c["met"] for c in (prev or {"checks": []})["checks"]}
        moved = [c for c in cur["checks"] if c["met"] and c["fact"] and was < names.index(c["stage"]) <= now]
        fresh = [c for c in moved if not before.get(c["id"])]
        if when and fresh:
            said = [when(c["fact"], c["call"]) for c in fresh]
            why = max(zip(fresh, said, range(len(fresh))), key=lambda x: (-1.0 if x[1] is None else x[1], x[2]))[0]
        else:
            why = next(iter(fresh), moved[0] if moved else None)
        if now != was or prev is None:
            out.append({"kind": "stage", "field": "stage", "fact": why and why["fact"], "call": why and why["call"],
                        "text": f"Stage moved to {cur['stage']}" if prev is None or now > was else
                        f"Stage went back to {cur['stage']}"})
    for key, label in LABELS.items():
        a = (prev or {"fields": {}})["fields"].get(key)
        b = cur["fields"].get(key)
        if b and (not a or a["fact"] != b["fact"]) and (not a or a.get("value") != b.get("value")):
            verb = "set" if not a else "changed"
            out.append({"kind": key, "field": key, "fact": b["fact"], "call": b.get("call"),
                        "text": f"{label} {verb}: {b.get('text') or b['value']}"})
    old_contacts = {c["name"] for c in (prev or {"fields": {}})["fields"].get("stakeholders") or []}
    for c in cur["fields"].get("stakeholders") or []:
        if c["name"] not in old_contacts:
            out.append({"kind": "contact", "field": "stakeholders", "fact": c["fact"], "call": c.get("call"),
                        "text": f"New contact: {c['name']}, {c['role'].lower()}"})
    for key, items in cur["fields"].items():
        if key in LABELS or key == "stakeholders" or not isinstance(items, list):
            continue
        before = _ids((prev or {"fields": {}})["fields"].get(key))
        for x in items:
            if x["fact"] in before or x.get("replaces"):
                continue
            kind = "risk" if key == "risks" else "commitment" if key == "commitments" else "fact"
            out.append({"kind": kind, "field": key, "fact": x["fact"], "call": x.get("call"),
                        "text": f"{'New risk' if kind == 'risk' else labels.get(key, key)}: {x['value']}"})
    if prev and call_date:
        for x in prev["fields"].get("commitments") or []:
            if x.get("kind") == "meeting" and x.get("date") == call_date:
                out.append({"kind": "kept", "field": "commitments", "fact": x["fact"], "call": x.get("call"),
                            "text": f"Commitment kept: {x['value']}"})
    return out
