"""site/index.html: the header, the five tab panels and How it works, rendered from WORDS.md and the results.

The Call, Deal, Email and Coach panels are filled by site/app.js from window.CC. How it works is rendered here, since
it reads the scores, the comparison, the claim checker's results and the recorded runs, which don't change in the
browser. Nothing inline: no script or style attributes, so the site's content security policy holds.
"""
import base64
import html
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
esc = lambda s: html.escape(str(s), quote=True)  # noqa: E731
MARK = ("<svg viewBox='0 0 32 32' xmlns='http://www.w3.org/2000/svg'><rect width='32' height='32' rx='8' "
        "fill='#0b5f57'/><path d='M7 18v-4M11 21V11M15 23V9M19 20v-8M23 17v-2' stroke='#fffdf9' stroke-width='2.4' "
        "stroke-linecap='round'/></svg>")
MARK_INLINE = MARK.replace("fill='#0b5f57'", "fill='currentColor'")


def day_label(iso):
    d = date.fromisoformat(iso)
    return f"{d.strftime('%B')} {d.day}"


def pct(x, digits=0):
    return "" if x is None else f"{x * 100:.{digits}f}%"


def dec(x):
    return "" if x is None else f"{x:.2f}"


def money(x):
    if x is None:
        return ""
    return f"${x:,.4f}" if x < 0.01 else f"${x:,.3f}" if x < 1 else f"${x:,.2f}"


def table(head, rows, cls="grid"):
    th = "".join(f"<th scope='col'>{esc(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<div class='table-wrap'><table class='{cls}'><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>"


def picker(w, calls):
    deal = [c for c in calls if c["kind"] == "deal"]
    scored = [c for c in calls if c["kind"] != "deal"]
    opt = lambda c, label: f"<option value='{esc(c['id'])}'>{esc(label)}</option>"  # noqa: E731
    a = "".join(opt(c, f"{i} · {c['title']} ({day_label(c['date'])})") for i, c in enumerate(deal, 1))
    b = "".join(opt(c, c["title"]) for c in scored)
    return (f"<label class='pick'><span>{esc(w['page.pick'])}</span><select id='pick-call'>"
            f"<optgroup label='{esc(w['page.pick.deal'])}'>{a}</optgroup>"
            f"<optgroup label='{esc(w['page.pick.scored'])}'>{b}</optgroup></select></label>")


def model_picker(w, models):
    opts = "".join(f"<option value='{esc(m['id'])}'>{esc(m['label'])}</option>" for m in models)
    return (f"<label class='pick'><span>{esc(w['page.model'])}</span><select id='pick-model'>{opts}</select>"
            f"</label>")


def how_map(w):
    kinds = w.table("how.map.legend")
    items = []
    for key, raw in w.table("how.map").items():
        title, text, kind = raw.split("|")
        items.append(f"<li class='step {esc(kind)}' data-box='{esc(key)}'><span class='kind'>{esc(kinds[kind])}</span>"
                     f"<strong>{esc(title)}</strong><span>{esc(text)}</span></li>")
    legend = "".join(f"<li class='{esc(k)}'><span class='swatch'></span>{esc(v)}</li>" for k, v in kinds.items())
    return (f"<section class='panel' id='how-map'><h3>{esc(w['how.map.title'])}</h3>"
            f"<ol class='pipeline'>{''.join(items)}</ol><ul class='legend'>{legend}</ul></section>")


def how_scores(w, data):
    res, cols, splits = data["results"], w.table("how.score.cols"), w.table("how.score.splits")
    labels = {m["id"]: m["label"] for m in data["models"]}
    rows = []
    for m in [x["id"] for x in data["models"]]:
        for s in ("test", "deal", "dev"):
            v = (res["scores"].get(m) or {}).get(s)
            if not v:
                continue
            nf = v["not_found"]
            rows.append([esc(labels.get(m, m)), esc(splits[s]), dec(v["f1"]), dec(v["precision"]), dec(v["recall"]),
                         pct(v["unsupported_rate"], 1), f"{nf['right']} of {nf['total']}"])
    body = table([cols[k] for k in ("model", "split", "f1", "precision", "recall", "held", "notfound")], rows) \
        if rows else f"<p class='muted'>{esc(w['how.score.none'])}</p>"
    miss = ""
    if res["misses"]:
        fields = w.table("ui.fields")
        items = "".join(f"<li><span class='tag'>{esc(fields.get(x['field'], x['field']))}</span>{esc(x['value'])} "
                        f"<span class='muted'>({esc(x['call'])})</span></li>" for x in res["misses"])
        miss = f"<h4>{esc(w['how.score.misses'])}</h4><ul class='misses'>{items}</ul>"
    return (f"<section class='panel' id='how-score'><h3>{esc(w['how.score.title'])}</h3>"
            f"<p>{esc(w['how.score.lead'])}</p>{body}{miss}</section>")


def how_compare(w, data):
    comp = data["results"]["comparison"]
    cols = w.table("how.compare.cols")
    # The routed model leads, as it does in the scoreboard above.
    ranked = sorted(comp["rows"], key=lambda r: r["model"] != comp["route"])
    rows = [[esc(r["label"]), dec(r["f1"]["test"]), pct(r["held_rate"], 1), str(r["flagged"]),
             money(r["cost_per_call"]), money(r["per_month_estimate"]), f"{r['seconds_per_call']:.1f}"]
            for r in ranked]
    body = table([cols[k] for k in ("model", "f1", "held", "flagged", "cost", "month", "time")], rows) \
        if rows else f"<p class='muted'>{esc(w['how.score.none'])}</p>"
    label = {m["id"]: m["label"] for m in data["models"]}.get(comp["route"], comp["route"])
    which = "how.compare.route" if comp.get("route_reason") == "cheapest_clearing" else "how.compare.best"
    bar = "{:.2f}".format(comp.get("f1_bar", 0.85))
    route = "<p>" + esc(w.fill(which, model=label, bar=bar)) + "</p>" if comp["route"] else ""
    local = f"<p>{esc(w['how.compare.local'])}</p>" if any(r["local"] for r in comp["rows"]) else ""
    # The sentence names the two Claude models and the ratio their recorded runs show, so it only goes in with both.
    both = {"claude-haiku", "claude-sonnet"} <= {r["model"] for r in comp["rows"]}
    think = f"<p>{esc(w['how.compare.thinking'])}</p>" if both else ""
    flags = f"<p>{esc(w['how.compare.flags'])}</p>" if any(r["flagged"] for r in comp["rows"]) else ""
    return (f"<section class='panel' id='how-compare'><h3>{esc(w['how.compare.title'])}</h3>"
            f"<p>{esc(w['how.compare.lead'])}</p>{body}{think}{flags}{route}{local}</section>")


def how_checker(w, data):
    r = data["results"]["claims"]
    if not r:
        return ""
    kinds = w.table("how.checker.kinds")
    rows = [[esc(kinds[k]), f"{v['caught']} of {v['planted']}"] for k, v in r["by_type"].items()]
    text = w.fill("how.checker", planted=r["planted"], clean=r["clean_emails"], caught=r["caught"],
                  alarms=r["false_alarm_emails"])
    miss = f"<p>{esc(w['how.checker.miss'])}</p>" if r["missed"] else ""
    return (f"<section class='panel' id='how-checker'><h3>{esc(w['how.checker.title'])}</h3><p>{esc(text)}</p>"
            f"{table(['', ''], rows, 'grid compact')}{miss}</section>")


def how_audio(w, data):
    wer, timing = data["results"]["wer"], data["results"]["timing"]
    cols = w.table("how.audio.cols")
    if not wer:
        return (f"<section class='panel' id='how-audio'><h3>{esc(w['how.audio.title'])}</h3>"
                f"<p>{esc(w['how.audio'])}</p><p class='muted'>{esc(w['how.audio.none'])}</p></section>")
    rows = []
    for call, v in wer["calls"].items():
        off = ((timing or {}).get("calls", {}).get(call) or {}).get("points_off")
        rows.append([esc(call), pct(v["overall"], 1), pct(v["seller"], 1), pct(v["buyer_phone"], 1),
                     pct(v["buyer_clean"], 1), "" if off is None else f"{off:.1f} points"])
    rows.append(["<strong>All</strong>", pct(wer["overall"], 1), pct(wer["seller"], 1), pct(wer["buyer_phone"], 1),
                 pct(wer["buyer_clean"], 1), "" if not timing else f"{timing['worst_points_off']:.1f} at most"])
    bar = ""
    if timing and "within" in timing:
        bar = "<p class='muted'>" + esc(w.fill("how.audio.bar", within=timing["within"], total=len(timing["calls"]))) + "</p>"
    return (f"<section class='panel' id='how-audio'><h3>{esc(w['how.audio.title'])}</h3><p>{esc(w['how.audio'])}</p>"
            f"{table([cols[k] for k in ('call', 'overall', 'seller', 'phone', 'clean', 'talk')], rows)}{bar}</section>")


def how_questions(w, data):
    q = data["results"].get("questions")
    if not q:
        return ""
    text = w.fill("how.questions", agree=f"{q['agreement']:.0%}", n=q["questions"],
                  first=f"{q['first_run']['agreement']:.0%}")
    return (f"<section class='panel' id='how-questions'><h3>{esc(w['how.questions.title'])}</h3><p>{esc(text)}</p>"
            f"</section>")


def how_runs(w, data):
    cols, steps = w.table("how.runs.cols"), w.table("how.runs.steps")
    labels = {m["id"]: m["label"] for m in data["models"]}
    rows = [[esc(labels.get(r["model"], r["model"])), esc(steps.get(r["step"], r["step"])), str(r["calls"]),
             esc(day_label(r["first"]) if r["first"] == r["last"] else f"{day_label(r['first'])} to "
                 f"{day_label(r['last'])}")] for r in data["results"]["runs"]]
    body = table([cols[k] for k in ("model", "step", "calls", "date")], rows) if rows else ""
    return (f"<section class='panel' id='how-runs'><h3>{esc(w['how.runs.title'])}</h3><p>{esc(w['how.runs'])}</p>"
            f"{body}</section>")


def how_code(w):
    feats = "".join(f"<button type='button' class='cfeat' data-file='{esc(path)}'><strong>{esc(label)}</strong>"
                    f"<code>{esc(path)}</code></button>" for path, label in w.table("how.code.feat").items())
    return (f"<section class='panel' id='how-code'><h3>{esc(w['how.code.title'])}</h3><p>{esc(w['how.code'])}</p>"
            f"<div class='code-featured'>{feats}</div><div class='code-view'>"
            f"<nav class='code-tree' id='code-tree' aria-label='{esc(w['how.code.tree'])}'></nav>"
            f"<div class='code-pane'><div class='code-head'><code id='code-path'></code></div>"
            f"<pre class='code' tabindex='0'><code id='code-body'></code></pre></div></div></section>")


def how(w, data):
    paras = lambda key: "".join(f"<p>{esc(p)}</p>" for p in w.paragraphs(key))  # noqa: E731
    local = any(r["local"] for r in data["results"]["comparison"]["rows"])
    privacy = paras("how.privacy") + (f"<p>{esc(w['how.privacy.local'])}</p>" if local else "")
    return ("<div class='how'>"
            f"<h2>{esc(w['how.title'])}</h2><p class='lead'>{esc(w['how.lead'])}</p>"
            f"{how_map(w)}"
            f"<section class='panel' id='how-calls'><h3>{esc(w['how.calls.title'])}</h3>{paras('how.calls')}"
            f"<p class='note'>{esc(w['how.calls.upper'])}</p></section>"
            f"{how_scores(w, data)}{how_compare(w, data)}{how_checker(w, data)}{how_audio(w, data)}"
            f"{how_questions(w, data)}"
            f"{how_runs(w, data)}"
            f"<section class='panel' id='how-privacy'><h3>{esc(w['how.privacy.title'])}</h3>{privacy}</section>"
            f"<section class='panel' id='how-limits'><h3>{esc(w['how.limits.title'])}</h3>{paras('how.limits')}"
            f"</section>{how_code(w)}</div>")


def render(w, data):
    """The shell. Three cards sit under a quiet top bar: the calls, the call, and what the call produced, with an SVG
    layer over them for the threads. How it works is a view of its own. The script fills every card."""
    panels = w.table("page.tabs")
    aria = w.table("page.aria")
    screens = "".join(f"<button type='button' data-screen='{k}' aria-controls='{k}'>{esc(v)}</button>"
                      for k, v in w.table("page.screens").items())
    seg = "".join(f"<button type='button' role='tab' id='tab-{k}' data-panel-tab='{k}' aria-controls='record-body' "
                  f"aria-selected='false' tabindex='-1'>{esc(v)}<span class='count' id='count-{k}'></span></button>"
                  for k, v in panels.items())
    icon = "data:image/svg+xml;base64," + base64.b64encode(MARK.encode()).decode()
    links = w.table("page.links")
    byline = (f"<p>{esc(w['page.byline'])} · <a href='https://ryansansbury.com/'>{esc(links['site'])}</a> · "
              f"<a href='https://github.com/ryansansbury/call_companion'>{esc(links['code'])}</a></p>")
    preview = (f"<div class='preview' role='status'><strong>{esc(w['page.preview'])}</strong></div>"
               if data["preview"] else "")
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<meta name='robots' content='index, follow'><meta name='referrer' content='no-referrer'>"
            f"<title>{esc(w['page.title'])}</title><link rel='icon' href='{icon}'>"
            "<link rel='stylesheet' href='app.css'></head><body class='mode-work'>"
            "<a class='skip' href='#main'>Skip to the content</a>"
            f"{preview}<header class='top'><div class='crumbs'><a class='brand' href='#' id='home'>"
            f"<span class='mark' aria-hidden='true'>{MARK_INLINE}</span><strong>{esc(w['page.title'])}</strong></a>"
            "<span class='sep' aria-hidden='true'>/</span><span class='up' id='crumb-deal'></span>"
            "<span class='sep' aria-hidden='true'>/</span><span class='here' id='crumb-call'></span></div>"
            f"<div class='top-right'><span class='recorded'><i aria-hidden='true'></i>{esc(w['page.recorded'])}</span>"
            f"{model_picker(w, data['models'])}<a class='textlink' href='#how' id='how-link'>{esc(w['page.how'])}</a>"
            f"<button type='button' class='btn' id='present'>{esc(w['page.present'])}</button></div></header>"
            f"<nav class='screens' id='screens' aria-label='{esc(aria['screens'])}'>{screens}</nav>"
            "<main id='main' tabindex='-1'><div class='work' id='work'>"
            f"<aside class='deal-pane' id='calls' aria-label='{esc(aria['calls'])}'><div id='call-list'></div>"
            f"<div class='pane-foot'><p>{esc(w['page.footer.short'])}</p>{byline}</div></aside>"
            f"<section class='callpane' id='call' aria-label='{esc(aria['call'])}'></section>"
            f"<aside class='record' id='record' aria-label='{esc(aria['record'])}'>"
            f"<div class='seg-control' role='tablist' aria-label='{esc(aria['panels'])}'>{seg}</div>"
            "<div class='record-body' id='record-body' role='tabpanel'></div></aside>"
            "<svg class='threads' id='threads' aria-hidden='true'></svg></div>"
            f"<section class='how-view' id='how' hidden><div class='how-top'><button type='button' class='btn' "
            f"id='how-back'>{esc(w['page.back'])}</button></div>{how(w, data)}"
            f"<footer class='how-foot'><p>{esc(w['page.footer'])}</p>{byline}</footer></section></main>"
            "<svg class='tour' id='tour' aria-hidden='true' hidden></svg>"
            "<div class='presenter' id='presenter' hidden></div><div class='pop' id='pop' hidden></div>"
            "<script src='claims.js'></script><script src='data.js'></script><script src='app.js'></script>"
            "</body></html>")


def write(text, path=None):
    path = Path(path or HERE.joinpath("site", "index.html"))
    path.write_text(text, encoding="utf-8")
    return path.stat().st_size
