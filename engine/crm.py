"""Turn checked facts into the seller's CRM record, and set the stage with the plain rules in config/crm.json.

A fact is {id, field, value, ...}: an item the evidence check kept, or a key fact in the tests. On the deal the
record builds across the calls in order, and each call's record is what the Deal tab shows after that call. Amount,
close date and next step take the newest call's value. The other fields keep every fact with the call it came from.
Contact roles come from the facts that name the economic buyer, the champion and the other stakeholders.

The stage is the furthest one whose rules, and every earlier stage's rules, are met. A rule the visitor switched off
counts as met. "dated_next_step" needs a next step with a date, "terms" needs a commitment of kind terms, and
"concessions_approved" needs every concession approved (and holds when there are none). The page recomputes the stage
from these same rule results, so it never disagrees with this file. Standard library only.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
CONTACT_ROLES = [("economic_buyer", "Economic buyer"), ("champion", "Champion"), ("stakeholders", "Influencer")]


def load():
    return json.loads(HERE.joinpath("config", "crm.json").read_text(encoding="utf-8"))


def _met(need, by, approved):
    """(met, the fact that meets it or blocks it) for one rule."""
    if need == "dated_next_step":
        hit = next((f for f in by.get("next_steps", []) if f.get("date")), None)
    elif need == "terms":
        hit = next((f for f in by.get("commitments", []) if f.get("kind") == "terms"), None)
    elif need == "concessions_approved":
        pending = [f for f in by.get("commitments", []) if f.get("kind") == "concession" and
                   not (f.get("approved") or f["id"] in approved)]
        return (not pending, pending[0] if pending else None)
    else:
        hit = next(iter(by.get(need, [])), None)
    return (hit is not None, hit)


def checks(by, cfg, approved=()):
    out = []
    for st in cfg["stages"]:
        for r in st["rules"]:
            met, fact = _met(r["needs"], by, set(approved))
            out.append({"stage": st["name"], "id": r["id"], "label": r["label"], "met": met,
                        "fact": fact["id"] if fact else None, "call": fact.get("call") if fact else None})
    return out


def stage(rule_checks, cfg, off=()):
    """The furthest stage whose rules, and every earlier stage's, are met or switched off."""
    reached = cfg["stages"][0]["name"]
    for st in cfg["stages"]:
        rules = [c for c in rule_checks if c["stage"] == st["name"]]
        if all(c["met"] or c["id"] in off for c in rules):
            reached = st["name"]
        else:
            break
    return reached


NAME_START = re.compile(r"^([A-Z][a-z]+(?: [A-Z][a-z]+)?),\s+(?:the\s+)?([^,.]+)")
FULL_NAME = re.compile(r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b")


def names_in(fact, roster=()):
    """(name, title or None) for each person a fact names."""
    if fact.get("name"):
        return [(fact["name"], fact.get("role"))]
    v = fact.get("value") or ""
    out = []
    m = NAME_START.match(v)
    if m:
        out.append((m.group(1), m.group(2).strip()))
    for m in FULL_NAME.finditer(v):
        if all(m.group(1) != n for n, _ in out) and not any(m.group(1).startswith(n + " ") for n, _ in out):
            out.append((m.group(1), None))
    for person in roster:
        first = person["name"].split()[0]
        if re.search(r"\b" + re.escape(first) + r"\b", v) and not any(n.split()[0] == first for n, _ in out):
            out.append((person["name"], None))
    return out


def contacts(by, roster=()):
    titles = {p["name"]: p.get("role") for p in roster}
    out = {}
    for field, label in CONTACT_ROLES:
        for f in by.get(field, []):
            for name, title in names_in(f, roster):
                full = next((p["name"] for p in roster if p["name"].split()[0] == name.split()[0]), name)
                if full not in out:
                    out[full] = {"name": full, "title": titles.get(full) or title, "role": label, "fact": f["id"],
                                 "call": f.get("call")}
    return list(out.values())


def same_fact(a, b):
    """Whether a later call's fact restates an earlier one: the same field, and the same number or mostly the same
    words. The record keeps the newer one and notes the call where it first came up."""
    from engine.claims import topic_words
    if a["field"] != b["field"]:
        return False
    if a.get("number") is not None and b.get("number") is not None:
        return abs(float(a["number"]) - float(b["number"])) < 1e-9
    x, y = set(topic_words(a["value"])), set(topic_words(b["value"]))
    return bool(x and y) and len(x & y) >= 0.5 * len(x | y)


def _newest(items):
    if not items:
        return []
    last = items[-1].get("call")
    return [f for f in items if f.get("call") == last]


def record(facts, cfg=None, approved=(), roster=(), call=None):
    """The CRM record from these facts, oldest first. Returns fields, rule checks and the stage."""
    cfg = cfg or load()
    by = {}
    for f in facts:
        by.setdefault(f["field"], []).append(f)
    fields = {}
    for fd in cfg["fields"]:
        kind = fd.get("kind", "list")
        items = [f for src in fd.get("from", []) for f in by.get(src, [])]
        if kind == "stage":
            continue
        if kind == "money":
            pick = next((f for f in reversed(_newest(items)) if f.get("number") is not None), None)
            fields[fd["key"]] = pick and {"value": pick["number"], "text": pick["value"], "fact": pick["id"],
                                          "call": pick.get("call")}
        elif kind == "date":
            dated = [f for f in _newest(items) if f.get("date")]
            pick = max(dated, key=lambda f: f["date"]) if dated else next(iter(_newest(items)), None)
            fields[fd["key"]] = pick and {"value": pick.get("date"), "text": pick["value"], "fact": pick["id"],
                                          "call": pick.get("call")}
        elif kind == "next":
            new = _newest(items)
            dated = sorted((f for f in new if f.get("date")), key=lambda f: f["date"])
            pick = dated[0] if dated else next(iter(new), None)
            fields[fd["key"]] = pick and {"value": pick["value"], "date": pick.get("date"), "fact": pick["id"],
                                          "call": pick.get("call")}
        elif kind == "contacts":
            fields[fd["key"]] = contacts(by, roster)
        else:
            kept = []
            for f in items:
                row = {"fact": f["id"], "value": f["value"], "call": f.get("call"), "date": f.get("date"),
                       "kind": f.get("kind"), "approved": f.get("approved")}
                same = next((i for i, x in enumerate(kept) if x["call"] != row["call"] and
                             same_fact(x["_src"], f)), None)
                if same is None:
                    kept.append(dict(row, _src=f))
                else:
                    older = kept[same]
                    kept[same] = dict(row, _src=f, replaces=older["fact"],
                                      first_call=older.get("first_call") or older["call"])
            fields[fd["key"]] = [{k: v for k, v in x.items() if k != "_src"} for x in kept]
    rule_checks = checks(by, cfg, approved)
    return {"call": call, "fields": fields, "checks": rule_checks, "stage": stage(rule_checks, cfg)}


def deal(calls, cfg=None, approved=(), roster=()):
    """One record per call, each building on the calls before it. calls is [(call id, [facts])] in order."""
    cfg = cfg or load()
    so_far, out = [], []
    for call, facts in calls:
        so_far = so_far + [dict(f, call=call) for f in facts]
        out.append(record(so_far, cfg, approved, roster, call))
    return out


def payload(rec, cfg=None):
    """The record as a Salesforce-style payload, keyed by API name."""
    cfg = cfg or load()
    out = {"attributes": {"type": cfg["object"]}, "StageName": rec["stage"]}
    for fd in cfg["fields"]:
        v = rec["fields"].get(fd["key"])
        kind = fd.get("kind", "list")
        if kind == "stage":
            continue
        if kind in ("money", "date"):
            out[fd["api"]] = v["value"] if v else None
        elif kind == "next":
            out[fd["api"]] = v["value"] if v else None
        elif kind == "contacts":
            out[fd["api"]] = [{"Name": c["name"], "Title": c["title"], "Role": c["role"]} for c in v]
        elif fd["key"] in ("next_steps", "commitments"):
            out[fd["api"]] = [{"Subject": x["value"], "ActivityDate": x.get("date")} for x in v]
        else:
            out[fd["api"]] = "\n".join(f"- {x['value']}" for x in v) or None
    return out
