"""Check a follow-up email against the call: every number, date, name and promise in it has to come from the call.

For each sentence it finds:
- money, percentages, and counts with a unit (trucks, sensors, rooms, days, minutes and the like);
- dates, resolved against the call's day ("Thursday," "the thirtieth," "October 2");
- people and companies the call never named, and a person given a role the call gave someone else;
- promises and concessions, from the words in config/policy.json ("waive," "at no cost," "discount").

A number or a date is supported when a checked fact holds it with the same unit. It's still flagged when the words
around it are plainly about a different fact that holds a different value. "$5,000 of seafood lost in that one load"
is caught although $5,000 is a real number from the call, since the call put $5,000 on the monthly credits and
$14,000 on the load. A concession is supported only once it's approved. Each claim comes back supported (with the
fact that backs it), unsupported (with the reason) or needing approval. It doesn't judge tone or paraphrased ideas,
which the page says.

table() turns a call's checked facts into everything the checks read, and the build writes that table into the page.
site/claims.js parses the email the same way and judges it against the same table, and tests/vectors/claims.json
holds the cases both must agree on.
"""
import json
import re
from datetime import date
from pathlib import Path

from engine import dates, numerals as numbers

HERE = Path(__file__).resolve().parent.parent

UNITS = {"truck": "truck", "trucks": "truck", "van": "van", "vans": "van", "trailer": "trailer",
         "trailers": "trailer", "sensor": "sensor", "sensors": "sensor", "probe": "probe", "probes": "probe",
         "cooler": "cooler", "coolers": "cooler", "walk-in": "walk-in", "walk-ins": "walk-in",
         "reach-in": "reach-in", "reach-ins": "reach-in", "room": "room", "rooms": "room", "store": "store",
         "stores": "store", "restaurant": "restaurant", "restaurants": "restaurant", "location": "location",
         "locations": "location", "vendor": "vendor", "vendors": "vendor", "box": "box", "boxes": "box",
         "excursion": "excursion", "excursions": "excursion", "day": "day", "days": "day", "week": "week",
         "weeks": "week", "month": "month", "months": "month", "year": "year", "years": "year", "hour": "hour",
         "hours": "hour", "minute": "minute", "minutes": "minute", "degree": "degree", "degrees": "degree",
         "percent": "percent", "%": "percent"}
PLURAL = {"box": "boxes", "percent": "percent"}
CURRENCY = ["usd", "dollar", "dollars", "bucks", "grand"]
STOP = sorted(set("""a about after again all also am an and any are as at be because been before being both but by
can could did do does doing done each even for from get gets got had has have he her here him his how i if in into
is it its just let me more most my no not now of off on once only or our out over own per same she should so some
still such than that the their them then there these they this those through to too under until up us very was we
well were what when where which while who why will with would yes yet you your send sends sent every""".split()))
NUMBER_WORDS = sorted(set(numbers.SMALL) | {"hundred", "thousand", "million", "half", "couple", "dozen"} |
                      set(dates.ORDINALS))
COMMON = sorted(set("""hi hello hey dear thanks thank best regards cheers sincerely talk looking great good glad
happy sorry please let i i'm i'll i'd i've we we'll we're we'd we've you you'll you're you'd your our it it's its this
that these those the a an as at by for from in on of to with next once when after before if since given also and but
so or here there attached following quick just again really per until meanwhile finally first then both each every
all any no not yes what why how who where which would could should can will do does did is are was were have has had
let's congrats welcome sounds hope sure absolutely definitely certainly perfect okay ok noted understood agreed
appreciate wonderful excellent apologies reminder update recap summary overview enclosed below above regarding re
fyi plus however therefore overall together tonight yesterday everyone team folks between unlike thursday's
mr ms mrs dr""".split()))
ROLES = {
    "cfo": ["cfo", "chief financial officer"],
    "coo": ["coo", "chief operating officer"],
    "ceo": ["ceo", "chief executive"],
    "owner": ["owner"],
    "it": ["it manager", "it director", "head of it"],
    "ops": ["director of operations", "operations director", "operations manager", "head of operations",
            "operations lead"],
    "vp": ["vp", "vice president"],
    "ae": ["account executive"],
    "se": ["sales engineer", "solutions engineer"],
    "counsel": ["counsel", "lawyer", "attorney"],
    "chef": ["chef"],
    "kitchen": ["kitchen manager"],
    "superintendent": ["superintendent"],
    "transportation": ["transportation manager"],
    "nutrition": ["nutrition services", "director of nutrition"],
    "logistics": ["director of logistics", "logistics director", "logistics manager"],
    "gm": ["general manager"],
    "dispatcher": ["dispatcher"],
}
DAYS = dates.DAYS
MONTHS = dates.MONTHS
WEEKDAY = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
MONTH = r"(?:january|february|march|april|may|june|july|august|september|october|november|december)"
DATE_SPAN = re.compile(r"\b(?:(?:next|this|by|on)\s+)?" + WEEKDAY + r"(?:\s+the\s+[a-z0-9-]+)?\b|\b" + MONTH +
                       r"\s+(?:the\s+)?[a-z0-9-]+\b|\bthe\s+[a-z0-9-]+\s+of\s+" + MONTH + r"\b|\bthe\s+(?:\d{1,2}"
                       r"(?:st|nd|rd|th)|first|second|third|fourth|fifth|tenth|fifteenth|twentieth|thirtieth|"
                       r"(?:twenty|thirty)[- ][a-z]+)\b|\btoday\b|\btomorrow\b", re.I)
BOUNDARY = re.compile(r"(?<!\d),(?!\d)|[;:()]|\b(?:and|but|so|while|because|which|then)\b", re.I)
NAME_TOKEN = re.compile(r"\b[A-Z][a-z]+(?:['’-][A-Za-z]+)*")
PERSON_BEFORE = re.compile(r"\b([A-Z][a-z]+)(?:\s+[A-Z][a-z]+)?(?:,\s+(?:(?:the|your|our|their|an?)\s+)?"
                           r"(?:(?!(?:and|or|but)\s)[a-z]+\s+){0,2}|\s+as\s+(?:(?:the|your|our|their|an?)\s+)?)$")
GENERIC = ["back", "break", "charge", "cost", "full", "money", "off", "price", "refund"]
PERSON_AFTER = re.compile(r",?\s+([A-Z][a-z]+)")


def load_policy():
    return json.loads(HERE.joinpath("config", "policy.json").read_text(encoding="utf-8"))


def lexicon():
    """The word lists the checks share. The build writes them into the page for site/claims.js."""
    return {"units": UNITS, "plural": PLURAL, "currency": CURRENCY, "stop": STOP, "number_words": NUMBER_WORDS,
            "common": COMMON, "roles": ROLES, "generic": GENERIC, "policy": load_policy()["needs_approval"]}


def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+", (text or "").strip())
    return [p for p in parts if p.strip()]


def stem(word):
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def topic_words(text):
    """The words that say what a phrase is about, without numbers, units, days or filler."""
    out = []
    low = (text or "").lower().replace("’", "'")
    for w in re.findall(r"[a-z]+(?:'[a-z]+)?", low):
        if w.endswith("'s"):
            w = w[:-2]
        if "'" in w or len(w) < 3 or w in STOP or w in UNITS or w in NUMBER_WORDS or w in DAYS or w in MONTHS:
            continue
        out.append(stem(w))
    return out


def clause(sentence, start, end, reach=6):
    """The words around a claim: up to six on each side, inside the commas and joining words around it."""
    lo, hi = 0, len(sentence)
    for m in BOUNDARY.finditer(sentence):
        if m.end() <= start:
            lo = m.end()
        elif m.start() >= end:
            hi = m.start()
            break
    before = [m for m in re.finditer(r"\S+", sentence[lo:start])][-reach:]
    after = [m for m in re.finditer(r"\S+", sentence[end:hi])][:reach]
    return " ".join([m.group(0) for m in before] + [sentence[start:end]] + [m.group(0) for m in after])


def unit_keys(unit):
    out = []
    for w in re.findall(r"%|[a-z]+(?:-[a-z]+)*", (unit or "").lower()):
        key = "usd" if w in CURRENCY else UNITS.get(w)
        if key and key not in out:
            out.append(key)
    return out


def _unit_after(text, end):
    """The unit right after a number, or one word later past an adjective ("six cold rooms")."""
    m = re.match(r"\s*-?(%|[a-z]+(?:-[a-z]+)*)(?:\s+([a-z]+(?:-[a-z]+)*))?", text[end:].lower())
    if not m:
        return None
    for i, word in enumerate((m.group(1), m.group(2))):
        if word is None:
            break
        if word in CURRENCY:
            return "usd"
        if word in UNITS:
            return UNITS[word]
        if i == 0 and (word in STOP or word in NUMBER_WORDS):
            break
    return None


def _date_claims(text, call_day):
    """Dates a sentence names. A weekday after "a," "last" or "every" ("on a Saturday night") is a past or general
    day, not a date, so it's skipped. "The first" in words is a date only after "by," "on," "until" and the like,
    since "the first month" isn't one."""
    found = []
    for m in DATE_SPAN.finditer(text):
        before = text[max(0, m.start() - 9):m.start()].lower()
        if re.search(r"\b(?:a|last|every)\s+$", before) and re.match(WEEKDAY, m.group(0), re.I):
            continue
        if re.fullmatch(r"the\s+[a-z-]+", m.group(0), re.I) and \
                not re.search(r"\b(?:by|on|until|till|before|after|from|of|through)\s+$", before):
            continue
        d = dates.resolve(m.group(0), call_day)
        if d:
            found.append({"kind": "date", "text": m.group(0), "start": m.start(), "end": m.end(),
                          "value": d.isoformat()})
    return found


def _number_claims(text, skip):
    """Money, percentages and counts, skipping spans already read as dates, years, and a bare "one." """
    found = []
    spans = numbers.spoken(text) + numbers.written(text)
    for value, s, e in sorted(spans, key=lambda x: x[1]):
        if any(a <= s < b for a, b in skip):
            continue
        raw = text[s:e].strip()
        low = raw.lower()
        if low.startswith("$"):
            unit = "usd"
        elif low.endswith("%") or low.endswith("percent"):
            unit = "percent"
        else:
            unit = _unit_after(text, e)
        if unit is None and 1900 <= value <= 2100:
            continue
        if unit is None and low == "one":
            continue
        found.append({"kind": "money" if unit == "usd" else "percent" if unit == "percent" else "count",
                      "text": raw, "start": s, "end": s + len(text[s:e].rstrip()), "value": value, "unit": unit})
    return found


def _word_at(low, phrase):
    return [m for m in re.finditer(r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])", low)]


def _promise_claims(text, policy):
    low, found = text.lower(), []
    for key, rule in policy.items():
        blocked = [(m.start(), m.end()) for x in rule.get("except", []) for m in _word_at(low, x)]
        hit = None
        for w in rule["words"]:
            for m in _word_at(low, w):
                if not any(a <= m.start() and m.end() <= b for a, b in blocked):
                    hit = m
                    break
            if hit:
                break
        if hit:
            found.append({"kind": "promise", "text": text[hit.start():hit.end()], "start": hit.start(),
                          "end": hit.end(), "rule": key, "label": rule["label"]})
    return found


def _name_key(token):
    t = token.lower().replace("’", "'")
    return t[:-2] if t.endswith("'s") else t


def _name_claims(sentence, tbl):
    """Capitalized words the call never said: a person or company nobody named. A word the call or the email uses
    in lowercase is an ordinary word. A sentence's first word counts only as part of a full name ("Kevin Smith") or
    with a possessive ("Kevin's"), since an ordinary word starts most sentences."""
    known, vocab = set(tbl["known"]), set(tbl["vocab"])
    lower_here = set(re.findall(r"\b[a-z][a-z'-]*", sentence))
    first = re.match(r"[\s\"'(]*", sentence).end()
    runs = []
    for m in NAME_TOKEN.finditer(sentence):
        if runs and sentence[runs[-1][-1].end():m.start()] == " ":
            runs[-1].append(m)
        else:
            runs.append([m])
    flagged = []
    for run in runs:
        for m in run:
            key = _name_key(m.group(0))
            if key in known or key in COMMON or key in DAYS or key in MONTHS or key in NUMBER_WORDS or \
                    key in vocab or key in lower_here or len(key) < 3:
                continue
            if m.start() == first and len(run) == 1 and key == m.group(0).lower():
                continue
            end = m.start() + len(key) if key != m.group(0).lower() else m.end()
            if flagged and sentence[flagged[-1]["end"]:m.start()] == " ":
                last = flagged[-1]
                last["end"] = end
                last["text"] = sentence[last["start"]:end]
            else:
                flagged.append({"kind": "name", "start": m.start(), "end": end, "text": sentence[m.start():end]})
    for c in flagged:
        c.update(status="unsupported", fact=None, check="unknown_name",
                 reason=f"{c['text']} isn't named anywhere in the call")
    return flagged


def role_keys(text):
    low = (text or "").lower()
    return sorted({key for key, phrases in ROLES.items() for p in phrases if _word_at(low, p)})


def _person_near(text, start, end, people):
    m = PERSON_BEFORE.search(text[:start])
    if m and m.group(1).lower() in people:
        return m.group(1).lower()
    m = PERSON_AFTER.match(text[end:])
    if m and m.group(1).lower() in people:
        return m.group(1).lower()
    return None


def role_mentions(text, people):
    """(person, role key) for each "Linda Marsh, the CFO" or "your CFO, Linda" in the text."""
    low, out = text.lower(), []
    for key, phrases in ROLES.items():
        for p in phrases:
            for m in _word_at(low, p):
                who = _person_near(text, m.start(), m.end(), people)
                if who:
                    out.append((who, key, m.start(), m.end()))
    return out


def _role_claims(sentence, tbl):
    out = []
    for who, key, s, e in role_mentions(sentence, set(tbl["roles"])):
        has = tbl["roles"].get(who) or []
        if has and key not in has:
            out.append({"kind": "role", "text": sentence[s:e], "start": s, "end": e, "value": key,
                        "status": "unsupported", "fact": None, "check": "role",
                        "reason": f"the call has {who.title()} as {tbl['role_text'][who]}"})
    return out


def claims_in(sentence, tbl, policy):
    day = date.fromisoformat(tbl["day"])
    ds = _date_claims(sentence, day)
    out = ds + _number_claims(sentence, [(c["start"], c["end"]) for c in ds]) + _promise_claims(sentence, policy)
    return sorted(out, key=lambda c: c["start"])


def _weight(word, tbl):
    return 2 if word in tbl["proper"] else 1


def _score(f, topic, tbl):
    return sum(_weight(w, tbl) for w in set(f["topic"]) & topic)


def _best(facts, topic, tbl):
    best, top = None, -1
    for f in facts:
        s = _score(f, topic, tbl)
        if s > top:
            best, top = f, s
    return best


def _conflict(claim, sentence, tbl, sup, others, show):
    """A fact the words are plainly about, holding a different value, outweighs the facts that hold this one."""
    if not others:
        return None
    topic = set(topic_words(clause(sentence, claim["start"], claim["end"])))
    s_best = max(_score(f, topic, tbl) for f in sup)
    rival = _best(others, topic, tbl)
    c = _score(rival, topic, tbl)
    if c >= 2 and c >= s_best + 2:
        return dict(claim, status="unsupported", fact=rival["id"], check="conflict",
                    reason=f"this is {show(rival)} in the call ({rival['id']})")
    return None


def _same(a, b):
    return abs(float(a) - float(b)) < 1e-9


def _has_unit(f, unit):
    return bool(_word_at(f["text"], unit) or _word_at(f["text"], unit + "s"))


def _holds(f, value, unit):
    for v, u in f["pairs"]:
        if _same(v, value) and (unit is None or u == unit or (u is None and _has_unit(f, unit))):
            return True
    return False


def show_number(value, unit):
    n = f"{value:,}" if isinstance(value, int) else f"{value:g}"
    if unit == "usd":
        return f"${n}"
    if unit == "percent":
        return f"{n}%"
    if unit is None:
        return n
    return f"{n} {unit if _same(value, 1) else PLURAL.get(unit, unit + 's')}"


def show_date(iso):
    d = date.fromisoformat(iso)
    return f"{DAYS[d.weekday()].title()}, {MONTHS[d.month - 1].title()} {d.day}"


def _judge_number(claim, sentence, tbl):
    sup = [f for f in tbl["facts"] if _holds(f, claim["value"], claim["unit"])]
    if not sup:
        return dict(claim, status="unsupported", fact=None, check="missing",
                    reason=f"no fact from the call has {show_number(claim['value'], claim['unit'])}")
    if claim["unit"] is not None:
        others = [f for f in tbl["facts"] if f not in sup and
                  any(u == claim["unit"] and not _same(v, claim["value"]) for v, u in f["pairs"])]

        def show(f):
            v = next(v for v, u in f["pairs"] if u == claim["unit"] and not _same(v, claim["value"]))
            return show_number(v, claim["unit"])
        hit = _conflict(claim, sentence, tbl, sup, others, show)
        if hit:
            return hit
    own = [f for f in sup if any(_same(v, claim["value"]) and (claim["unit"] is None or u == claim["unit"])
                                 for v, u in f["own"])]
    return _supported(claim, sentence, tbl, own or sup)


def _supported(claim, sentence, tbl, sup):
    """Supported, linked to the fact the words are most about. Facts whose own value holds the claim go first."""
    topic = set(topic_words(clause(sentence, claim["start"], claim["end"])))
    f = _best(sup, topic, tbl)
    return dict(claim, status="supported", fact=f["id"], check=None, reason=f"matches {f['id']}")


def _judge_date(claim, sentence, tbl):
    if claim["value"] == tbl["day"]:
        return dict(claim, status="supported", fact=None, check=None, reason="the day of the call")
    sup = [f for f in tbl["facts"] if claim["value"] in f["dates"]]
    if not sup:
        return dict(claim, status="unsupported", fact=None, check="missing",
                    reason=f"no fact from the call is dated {show_date(claim['value'])}")
    others = [f for f in tbl["facts"] if f not in sup and f["dates"]]
    hit = _conflict(claim, sentence, tbl, sup, others, lambda f: show_date(f.get("date") or f["dates"][0]))
    if hit:
        return hit
    own = [f for f in sup if claim["value"] in f["own_dates"]]
    return _supported(claim, sentence, tbl, own or sup)


def _judge_promise(claim, sentence, tbl, policy):
    words = policy[claim["rule"]]["words"]
    skip = {stem(w) for r in policy.values() for w in r["words"] if re.fullmatch(r"[a-z]+", w)} | set(GENERIC)
    topic = set(topic_words(clause(sentence, claim["start"], claim["end"]))) - skip
    for f in tbl["facts"]:
        if f.get("kind") != "concession":
            continue
        if f.get("policy") != claim["rule"] and not any(_word_at(f["text"], w) for w in words):
            continue
        if (set(f["topic"]) - skip) & topic:
            if f.get("approved"):
                return dict(claim, status="supported", fact=f["id"], check=None, reason=f"approved, {f['id']}")
            return dict(claim, status="needs_approval", fact=f["id"], check="approval",
                        reason=f"{claim['label'].lower()} need a manager's approval first")
    return dict(claim, status="unsupported", fact=None, check="promise", reason="nobody offered this on the call")


def judge(claim, sentence, tbl, policy):
    if claim["kind"] == "date":
        return _judge_date(claim, sentence, tbl)
    if claim["kind"] == "promise":
        return _judge_promise(claim, sentence, tbl, policy)
    return _judge_number(claim, sentence, tbl)


def check_email(text, tbl, policy=None):
    """[{sentence, claims: [...]}] for the whole email, every claim judged, in order."""
    policy = policy or load_policy()["needs_approval"]
    out = []
    for s in sentences(text):
        judged = [judge(c, s, tbl, policy) for c in claims_in(s, tbl, policy)]
        judged += _name_claims(s, tbl) + _role_claims(s, tbl)
        out.append({"sentence": s, "claims": sorted(judged, key=lambda c: c["start"])})
    return out


def dates_in(text, call_day):
    """Every date a piece of text names, as ISO strings."""
    if isinstance(call_day, str):
        call_day = date.fromisoformat(call_day)
    return sorted({c["value"] for c in _date_claims(text or "", call_day)})


def number_pairs(text):
    """(value, unit) for every number in a fact's text, with None for a bare number."""
    ds = _date_claims(text, date(2026, 1, 1))
    seen, out = set(), []
    for c in _number_claims(text, [(d["start"], d["end"]) for d in ds]):
        if (c["value"], c["unit"]) not in seen:
            seen.add((c["value"], c["unit"]))
            out.append([c["value"], c["unit"]])
    return out


def table(facts, call_day, people=(), companies=(), transcript=""):
    """Everything the checks read for one call: the facts with their dates, numbers and topic words, the names the
    call said, everyday words that start sentences, and each person's roles."""
    if isinstance(call_day, str):
        call_day = date.fromisoformat(call_day)
    texts = [transcript or ""] + [f.get("value") or "" for f in facts] + \
        [q for f in facts for q in f.get("quotes") or []]
    call_text = "\n".join(texts)
    vocab = set(re.findall(r"\b[a-z][a-z'-]*", call_text))
    known = set()
    for p in people:
        known |= {w.lower() for w in re.findall(r"[A-Za-z]+", p["name"])}
    for c in companies:
        known |= {w.lower() for w in re.findall(r"[A-Za-z]+", c)}
    known |= {_name_key(m.group(0)) for m in NAME_TOKEN.finditer(call_text)}
    proper = sorted({stem(k) for k in known if k not in vocab and k not in COMMON and "'" not in k})
    roles, role_text = {}, {}
    for p in people:
        keys = role_keys(p.get("role"))
        for w in re.findall(r"[A-Za-z]+", p["name"]):
            roles.setdefault(w.lower(), set()).update(keys)
            if p.get("role"):
                role = p["role"]
                role_text.setdefault(w.lower(), role if role[:2].isupper() else role[0].lower() + role[1:])
    names = set(roles) | {k for k in known if k not in vocab and k not in COMMON}
    for who, key, s, e in role_mentions(call_text, names):
        roles.setdefault(who, set()).add(key)
        role_text.setdefault(who, call_text[s:e])
    rows = []
    for f in facts:
        text = " ".join([f.get("value") or ""] + list(f.get("quotes") or []))
        ds = set(dates_in(text, call_day))
        if f.get("date"):
            ds.add(f["date"])
        own = number_pairs(f.get("value") or "")
        if f.get("number") is not None:
            for u in unit_keys(f.get("unit")) or [None]:
                if [f["number"], u] not in own:
                    own.append([f["number"], u])
        pairs = own + [p for p in number_pairs(text) if p not in own]
        own_dates = set(dates_in(f.get("value") or "", call_day)) | ({f["date"]} if f.get("date") else set())
        rows.append({"id": f["id"], "field": f["field"], "value": f["value"], "kind": f.get("kind"),
                     "approved": bool(f["approved"]) if f.get("approved") is not None else f.get("kind") != "concession",
                     "policy": f.get("policy"), "date": f.get("date"), "dates": sorted(ds), "pairs": pairs,
                     "own": own, "own_dates": sorted(own_dates),
                     "topic": sorted(set(topic_words(f["value"]))), "text": text.lower()})
    return {"day": call_day.isoformat(), "facts": rows, "known": sorted(known), "vocab": sorted(vocab),
            "proper": proper, "roles": {k: sorted(v) for k, v in sorted(roles.items())},
            "role_text": dict(sorted(role_text.items()))}


def approve(tbl, ids):
    """A copy of the table with these concessions approved, for the page's toggle and the approved draft."""
    ids = set(ids)
    return dict(tbl, facts=[dict(f, approved=True) if f["id"] in ids else f for f in tbl["facts"]])


def summary(result):
    counts = {"supported": 0, "unsupported": 0, "needs_approval": 0}
    for s in result:
        for c in s["claims"]:
            counts[c["status"]] += 1
    return counts
