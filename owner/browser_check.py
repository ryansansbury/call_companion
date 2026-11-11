"""The owner's machine only. Look at the page in real Chrome: screenshots, the line rule, overlaps, console errors,
network requests and a seek test. Adapted from the Analyst Desk's browser check.

    bash owner/screenshots.sh            (from the build folder)

It opens the page in headless Chrome with a fresh profile and drives it over the DevTools pipe, once straight from the
file system and once from a small server on 127.0.0.1, which is how the live site loads audio (whole, into a blob).
Everything goes to owner/out/, which is gitignored:

    screens/card-1600.png         the page as a fresh load opens it at 1600 by 1000 with nothing clicked, the homepage
                                  card frame, so the card shows what a click on it opens
    screens/gallery-<panel>.png   call 3's Deal, Email (with one bad claim added), and Coach at the same size, for the
                                  README's gallery
    screens/<width>-<panel>-<call>.png  every panel for the first and last deal call at 1440 and 1280 (the narrow
                                  strip), and for the last at 1024
    screens/<width>-how.png       How it works
    screens/<width>-stepNN.png    what the shared screen shows after each presenter step, at 1440 and 1280
    screens/card-1600-replay.png  the card frame during a replay, the moment a fact lands
    screens/<width>-screen-*.png  on a phone and a narrow tablet, the three screens and the record on every panel
    screens/1440-replay-*.png     the replay mid-call on Fields and Deal, and the email filling in at the end
    layout.json                   last lines under 80% full, text overlapping text that a reader can see (scrolled-off
                                  text and text under a sticky header don't count), boxes whose content spills past
                                  their edge, anything wider than the window, and each shot's threads
    console.json, network.json    anything the page logged as an error, and every request it made
    seek.json                     the seek test: play, jump to 2 minutes, and check the clock and the transcript follow
    browser_check.json            the summary this prints

Standard library only.
"""
import argparse
import base64
import functools
import http.server
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SITE = ROOT.joinpath("site")
OUT = HERE.joinpath("out")
SHOTS = OUT.joinpath("screens")
APPS = Path("/").joinpath("Applications")
CHROMES = (APPS.joinpath("Google Chrome.app", "Contents", "MacOS", "Google Chrome"),
           APPS.joinpath("Chromium.app", "Contents", "MacOS", "Chromium"))
WIDTHS = ((1440, 900), (1280, 720))
SMALL = ((1024, 768), (768, 1024), (390, 844))
PANELS = ("fields", "deal", "email", "coach")
CALLS = ("deal-1", "deal-3")
SETTLE = 2.2
THREADS_JS = ("(function () { var p = document.querySelectorAll('#threads path.thread'); var bad = 0; "
              "p.forEach(function (x) { if (/NaN/.test(x.getAttribute('d'))) { bad += 1; } }); "
              "return {threads: p.length, link: document.querySelectorAll('#threads .link').length, bad: bad}; })()")
TRAMPOLINE = 'exec "$@" 3<&0 4>&1 0</dev/null 1>&2'

LAYOUT_JS = """(function () {
  var W = window.innerWidth, out = {wider_than_window: document.documentElement.scrollWidth > W + 1, overlaps: [],
    short_last_lines: [], spills: []};
  var root = document.body, boxes = new Map(), covers = [];
  function name(el) {
    return (el.id ? '#' + el.id : el.tagName.toLowerCase() + Array.prototype.map.call(el.classList, function (c) {
      return '.' + c; }).join('')).slice(0, 50);
  }
  function clip(el) {
    if (boxes.has(el)) { return boxes.get(el); }
    var b = {l: -1e9, t: -1e9, r: 1e9, b: 1e9};
    for (var a = el; a && a !== document.documentElement; a = a.parentElement) {
      var cs = getComputedStyle(a);
      if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') {
        var q = a.getBoundingClientRect();
        b = {l: Math.max(b.l, q.left), t: Math.max(b.t, q.top), r: Math.min(b.r, q.right), b: Math.min(b.b, q.bottom)};
      }
    }
    boxes.set(el, b);
    return b;
  }
  root.querySelectorAll('*').forEach(function (el) {
    if (el.closest('svg') || !el.checkVisibility()) { return; }
    var cs = getComputedStyle(el);
    if (cs.position === 'sticky' || cs.position === 'fixed' || el.matches('.pop')) { covers.push(el); }
    if (out.spills.length >= 25 || el.closest('pre, .code-tree, .sr') || cs.display === 'inline' || !el.clientWidth) { return; }
    if (/x|both/.test(cs.scrollSnapType || '')) { return; }
    if (el.scrollWidth > el.clientWidth + 1) {
      var scrolls = cs.overflowX === 'auto' || cs.overflowX === 'scroll';
      out.spills.push(name(el) + ' by ' + (el.scrollWidth - el.clientWidth) + 'px' + (scrolls ? ' (scrolls)' : ''));
    }
  });
  function covered(el, f) {
    return covers.some(function (c) {
      if (c === el || c.contains(el)) { return false; }
      var q = c.getBoundingClientRect();
      return f.l < q.right && f.r > q.left && f.t < q.bottom && f.b > q.top;
    });
  }
  root.querySelectorAll('p, li, dd, h2, h3, h4').forEach(function (el) {
    if (el.closest('pre, .code-tree, .transcript-pane, .findings, .chips') || !el.checkVisibility() ||
        el.querySelector('.chip, button, input, select, label')) { return; }
    var r = document.createRange(); r.selectNodeContents(el);
    var rects = Array.prototype.filter.call(r.getClientRects(), function (x) { return x.width > 1; });
    if (rects.length < 2) { return; }
    var tops = {}, box = el.getBoundingClientRect();
    rects.forEach(function (x) { var k = Math.round(x.top); tops[k] = Math.max(tops[k] || 0, x.right); });
    var keys = Object.keys(tops).map(Number).sort(function (a, b) { return a - b; });
    if (keys.length < 2) { return; }
    var lastRight = tops[keys[keys.length - 1]], fill = (lastRight - box.left) / Math.max(1, box.width);
    if (fill < 0.8) { out.short_last_lines.push({text: el.textContent.trim().slice(-60), fill: Math.round(fill * 100)}); }
  });
  var frags = [], walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), node, range = document.createRange();
  while ((node = walker.nextNode())) {
    var el = node.parentElement;
    if (!/\\S/.test(node.data) || !el || el.closest('script, style, pre, .code-tree') || !el.checkVisibility()) { continue; }
    var box = clip(el);
    range.selectNodeContents(node);
    Array.prototype.forEach.call(range.getClientRects(), function (x) {
      if (x.width < 1 || x.height < 1) { return; }
      var h = x.bottom - x.top, mid = (x.top + x.bottom) / 2;
      var f = {el: el, l: Math.max(x.left, box.l), r: Math.min(x.right, box.r), t: x.top + h * 0.2, b: x.bottom - h * 0.2,
        text: node.data.trim().slice(0, 40)};
      if (mid < box.t || mid > box.b || f.r - f.l < 1 || covered(el, f)) { return; }
      frags.push(f);
    });
  }
  frags.sort(function (a, b) { return a.t - b.t; });
  for (var i = 0; i < frags.length && out.overlaps.length < 20; i++) {
    for (var j = i + 1; j < frags.length && frags[j].t < frags[i].b; j++) {
      var f = frags[i], g = frags[j];
      if (f.el === g.el || f.el.contains(g.el) || g.el.contains(f.el)) { continue; }
      if (Math.min(f.r, g.r) - Math.max(f.l, g.l) > 2) { out.overlaps.push(f.text + ' / ' + g.text); }
    }
  }
  return out;
})()"""


def find_chrome(given=None):
    if given:
        return str(given)
    for p in CHROMES:
        if p.exists():
            return str(p)
    for n in ("google-chrome", "chromium"):
        if shutil.which(n):
            return shutil.which(n)
    raise SystemExit("Chrome wasn't found. Run again with --chrome and the path to the Chrome program.")


class CDP:
    """The DevTools protocol over Chrome's pipe: JSON messages, each ended by a zero byte."""

    def __init__(self, proc, on_event=None):
        self.proc, self.on_event = proc, on_event
        self.next_id, self.responses, self.events = 0, {}, []
        self.cond, self.wlock = threading.Condition(), threading.Lock()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        buf = b""
        while True:
            chunk = self.proc.stdout.read1(1 << 16)
            if not chunk:
                break
            buf += chunk
            while b"\0" in buf:
                raw, buf = buf.split(b"\0", 1)
                msg = json.loads(raw)
                with self.cond:
                    if "id" in msg:
                        self.responses[msg["id"]] = msg
                    else:
                        self.events.append(msg)
                    self.cond.notify_all()
                if "id" not in msg and self.on_event:
                    self.on_event(msg)

    def send(self, method, params=None, session=None, timeout=60):
        with self.cond:
            self.next_id += 1
            mid = self.next_id
        msg = {"id": mid, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        with self.wlock:
            self.proc.stdin.write(json.dumps(msg).encode() + b"\0")
            self.proc.stdin.flush()
        deadline = time.time() + timeout
        with self.cond:
            while mid not in self.responses:
                left = deadline - time.time()
                if left <= 0:
                    raise TimeoutError(method)
                self.cond.wait(left)
            reply = self.responses.pop(mid)
        if "error" in reply:
            raise RuntimeError(f"{method}: {reply['error'].get('message')}")
        return reply.get("result", {})

    def mark(self):
        with self.cond:
            return len(self.events)

    def wait_event(self, method, session, since, timeout=60):
        deadline = time.time() + timeout
        with self.cond:
            while True:
                for e in self.events[since:]:
                    if e.get("method") == method and e.get("sessionId") == session:
                        return e
                left = deadline - time.time()
                if left <= 0:
                    raise TimeoutError(method)
                self.cond.wait(left)


class Browser:
    def __init__(self, chrome):
        self.requests, self.console, self.loads = [], [], 0
        profile = OUT.joinpath("chrome-profile")
        shutil.rmtree(profile, ignore_errors=True)
        flags = ["--headless=new", "--remote-debugging-pipe", f"--user-data-dir={profile}", "--no-first-run",
                 "--no-default-browser-check", "--disable-extensions", "--hide-scrollbars", "--mute-audio",
                 "--disable-background-networking", "--disable-sync", "--disable-component-update",
                 "--autoplay-policy=no-user-gesture-required", "--allow-file-access-from-files"]
        self.log = OUT.joinpath("chrome.log").open("wb")
        self.proc = subprocess.Popen(["bash", "-c", TRAMPOLINE, "chrome", chrome, *flags], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=self.log)
        self.cdp = CDP(self.proc, self.event)
        target = self.cdp.send("Target.createTarget", {"url": "about:blank"})["targetId"]
        self.s = self.cdp.send("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
        for m in ("Page.enable", "Runtime.enable", "Network.enable", "Log.enable"):
            self.cdp.send(m, session=self.s)

    def event(self, e):
        m, p = e.get("method"), e.get("params", {})
        if m == "Network.requestWillBeSent":
            self.requests.append(p["request"]["url"])
        elif m == "Runtime.exceptionThrown":
            d = p["exceptionDetails"]
            self.console.append({"kind": "exception", "text": (d.get("exception") or {}).get("description") or d.get("text")})
        elif m == "Runtime.consoleAPICalled" and p.get("type") in ("error", "assert"):
            self.console.append({"kind": "console.error", "text": " ".join(str(a.get("value", a.get("description")))
                                                                           for a in p.get("args", []))})
        elif m == "Log.entryAdded" and p["entry"].get("level") == "error":
            self.console.append({"kind": "log", "text": p["entry"].get("text"), "url": p["entry"].get("url")})

    def view(self, width, height, mobile=False):
        self.cdp.send("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1,
                                                             "mobile": mobile}, self.s)

    def load(self, url):
        """A fresh page at the address. Each load carries its own query, so it is never a move within the same page,
        which fires no load event, and a reload can't race the page's own address change."""
        self.loads += 1
        base, mark, frag = url.partition("#")
        fresh = f"{base}{'&' if '?' in base else '?'}load={self.loads}{mark}{frag}"
        since = self.cdp.mark()
        self.cdp.send("Page.navigate", {"url": fresh}, self.s)
        self.cdp.wait_event("Page.loadEventFired", self.s, since)
        self.pause(0.5)

    def js(self, expr, wait=False):
        r = self.cdp.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": wait}, self.s)
        if "exceptionDetails" in r:
            raise RuntimeError(f"{expr[:60]}: {r['exceptionDetails'].get('text')}")
        return r.get("result", {}).get("value")

    def pause(self, seconds):
        self.js(f"new Promise(r => requestAnimationFrame(() => setTimeout(r, {int(seconds * 1000)})))", wait=True)

    def shot(self, name, width, full=True):
        params = {"format": "png"}
        if full:
            size = self.cdp.send("Page.getLayoutMetrics", session=self.s)["cssContentSize"]
            params.update(captureBeyondViewport=True, clip={"x": 0, "y": 0, "width": width,
                                                            "height": min(size["height"], 9000), "scale": 1})
        data = self.cdp.send("Page.captureScreenshot", params, self.s, timeout=120)["data"]
        SHOTS.joinpath(f"{name}.png").write_bytes(base64.b64decode(data))

    def close(self):
        try:
            self.cdp.send("Browser.close", timeout=10)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.log.close()


def go(b, panel, call):
    """Opens a call and a panel the way a visitor would, by clicking them, then waits out the threads drawing in (a
    panel with 29 items takes about 1.7 seconds)."""
    b.js("(function () { if (CCP.view() !== 'work') { document.getElementById('how-back').click(); } "
         f"var c = document.querySelector('[data-pick={call}]'); if (c) {{ c.click(); }} "
         f"var p = document.querySelector('[data-panel-tab={panel}]'); if (p) {{ p.click(); }} }})()")
    b.pause(SETTLE)


def serve(root):
    """The site on 127.0.0.1 so the page takes its http path, which fetches the audio whole into a blob."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def screen(b, name):
    b.js(f"document.querySelector('[data-screen={name}]').click()")
    b.pause(0.9)


def phone_shots(b, width, layout):
    """A phone or a narrow tablet: the three screens, the record screen on every panel, and one tour step."""
    go(b, "fields", "deal-3")
    for name in ("calls", "call"):
        screen(b, name)
        b.shot(f"{width}-screen-{name}", width, full=False)
        layout[f"{width}-screen-{name}"] = b.js(LAYOUT_JS)
    screen(b, "record")
    for panel in PANELS:
        b.js(f"document.querySelector('[data-panel-tab={panel}]').click()")
        b.pause(0.8)
        b.shot(f"{width}-screen-record-{panel}", width, full=False)
        layout[f"{width}-screen-record-{panel}"] = b.js(LAYOUT_JS)
    layout[f"screen_after_swipes_{width}"] = b.js("CCP.screen()")
    b.js("CCP.present(6)")
    b.pause(SETTLE)
    b.shot(f"{width}-tour-step06", width, full=False)
    b.js("CCP.present(0)")
    b.pause(0.4)


def scrub(b, t):
    b.js(f"(function () {{ var s = document.getElementById('scrub'); s.value = String(Math.round({t} * 10)); "
         "s.dispatchEvent(new Event('input', {bubbles: true})); })()")


def replay_shots(b, base, layout):
    """The replay: the card frame caught as a fact lands, then Fields and Deal mid-call on the last deal call and the
    email filling in when the call ends. Each start is paused and moved with the scrub so every shot is the same."""
    b.view(1600, 1000)
    b.load(base + "#fields/deal-1")
    b.js("document.getElementById('replay').click()")
    b.pause(0.3)
    b.js("if (CCP.state().playing) { document.getElementById('play').click(); }")
    land = b.js("(function () { var c = CC.calls.filter(function (x) { return x.id === 'deal-1'; })[0], a = c.ai[CCP.state().model] "
                "|| c.ai[Object.keys(c.ai)[0]], f = a.facts.filter(function (x) { return x.field === 'metrics'; })[0]; "
                "return f ? CCP.factAt('deal-1', f.id) : 60; })()") or 60
    scrub(b, land - 2.0)
    b.pause(1.6)
    scrub(b, land + 0.1)
    b.pause(0.45)
    b.shot("card-1600-replay", 1600, full=False)
    layout["card-1600-replay"] = b.js(LAYOUT_JS)
    layout["threads-card-1600-replay"] = b.js(THREADS_JS)
    b.view(1440, 900)
    b.load(base + "#fields/deal-3")
    b.js("document.getElementById('replay').click()")
    b.pause(0.3)
    b.js("if (CCP.state().playing) { document.getElementById('play').click(); }")
    for t, panel in ((75, "fields"), (75, "deal"), (130, "deal")):
        b.js(f"document.querySelector('[data-panel-tab={panel}]').click()")
        scrub(b, t)
        b.pause(SETTLE)
        name = f"1440-replay-{panel}-{t:03d}"
        b.shot(name, 1440, full=False)
        layout[name] = b.js(LAYOUT_JS)
        layout[f"threads-{name}"] = b.js(THREADS_JS)
    b.js("document.querySelector('[data-panel-tab=email]').click()")
    scrub(b, 100000)
    b.pause(SETTLE)
    b.shot("1440-replay-email-end", 1440, full=False)
    layout["1440-replay-email-end"] = b.js(LAYOUT_JS)
    layout["replay_ended"] = b.js("CCP.state().replay === false")


def seek_test(b, base):
    """Play deal-1, jump to two minutes and read the clock, the audio's own time and the highlighted segment. The
    development preview has no audio, so there the page's own clock is timed instead and the result says so. A real
    build has to pass on the audio."""
    b.load(base + "#fields/deal-1")
    b.js("document.getElementById('play').click()")
    b.pause(3.0)
    before = b.js("CCP.state()")
    b.js("document.getElementById('scrub').value = '1200'; document.getElementById('scrub').dispatchEvent(new Event('input', "
         "{bubbles: true}))")
    b.pause(1.5)
    after = b.js("CCP.state()") or {}
    preview = bool(b.js("!!document.querySelector('.preview')"))
    timed_by = "audio" if after.get("audio") is not None else "page clock"
    at = after.get("audio") if timed_by == "audio" else after.get("t")
    ok = bool(at is not None and 120 <= at <= 124 and after.get("playing") and (timed_by == "audio" or preview))
    return {"url": base, "timed_by": timed_by, "preview": preview, "before": before, "after": after, "passes": ok,
            "clock": b.js("document.getElementById('clock').textContent"),
            "segment_time": b.js("(document.querySelector('.seg.now .time') || {}).textContent || null")}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check the page in real Chrome and take its screenshots.")
    ap.add_argument("--chrome", help="the path to the Chrome program, if it isn't in the usual place")
    a = ap.parse_args(argv)
    shutil.rmtree(SHOTS, ignore_errors=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    # The run checks a copy of the page taken as it starts, so edits made to site/ while it runs can't change a shot.
    site = OUT.joinpath("site")
    shutil.rmtree(site, ignore_errors=True)
    shutil.copytree(SITE, site)
    url = site.joinpath("index.html").resolve().as_uri()
    b = Browser(find_chrome(a.chrome))
    layout, seeks, t0 = {}, [], time.time()
    httpd = serve(site)
    try:
        b.view(1600, 1000)
        home = f"http://127.0.0.1:{httpd.server_address[1]}/index.html"
        # The homepage card is the page exactly as a click on the card opens it, a fresh load with nothing clicked.
        b.load(home)
        b.pause(SETTLE + 0.6)
        b.shot("card-1600", 1600, full=False)
        layout["card-1600"] = b.js(LAYOUT_JS)
        layout["threads-card-1600"] = b.js(THREADS_JS)
        # The README's gallery at the same size. Deal and Coach as they open, and Email with one bad claim added so the
        # checker shows a flag.
        for panel in ("deal", "email", "coach"):
            b.load(f"{home}#{panel}/deal-3")
            b.pause(0.6)
            if panel == "email":
                b.js("(function () { var s = document.querySelector('[data-sample=money]'); if (s) { s.click(); } "
                     "var c = document.getElementById('checked'); if (c) { c.scrollIntoView({block: 'start'}); } })()")
            b.pause(SETTLE)
            b.shot(f"gallery-{panel}", 1600, full=False)
            layout[f"gallery-{panel}"] = b.js(LAYOUT_JS)
            layout[f"threads-gallery-{panel}"] = b.js(THREADS_JS)
        for width, height in WIDTHS:
            b.view(width, height)
            b.load(url)
            b.pause(1.0)
            for call in CALLS:
                for panel in PANELS:
                    go(b, panel, call)
                    b.shot(f"{width}-{panel}-{call}", width, full=False)
                    layout[f"{width}-{panel}-{call}"] = b.js(LAYOUT_JS)
                    layout[f"threads-{width}-{panel}-{call}"] = b.js(THREADS_JS)
            b.js("document.getElementById('how-link').click()")
            b.pause(0.8)
            b.shot(f"{width}-how", width)
            layout[f"{width}-how"] = b.js(LAYOUT_JS)
            b.load(url)
            steps = b.js("CCP.steps") or 0
            b.js("document.getElementById('present').click()")
            for i in range(1, steps + 1):
                b.pause(SETTLE)
                b.shot(f"{width}-step{i:02d}", width, full=False)
                layout[f"{width}-step{i:02d}"] = b.js(LAYOUT_JS)
                b.js("document.querySelector('[data-present=next]').click()")
        for width, height in SMALL:
            b.view(width, height, mobile=width < 500)
            b.load(url)
            if width > 900:
                for panel in PANELS:
                    go(b, panel, "deal-3")
                    b.shot(f"{width}-{panel}-deal-3", width)
                    layout[f"{width}-{panel}-deal-3"] = b.js(LAYOUT_JS)
            else:
                phone_shots(b, width, layout)
            layout[f"tabs_one_line_{width}"] = b.js("(function () { var t = document.querySelectorAll('[data-panel-tab]'); "
                                                     "var tops = Array.prototype.map.call(t, function (e) { return "
                                                     "Math.round(e.getBoundingClientRect().top); }); return tops.every("
                                                     "function (x) { return x === tops[0]; }); })()")
        replay_shots(b, url, layout)
        b.view(1440, 900)
        seeks.append(seek_test(b, url))
        seeks.append(seek_test(b, f"http://127.0.0.1:{httpd.server_address[1]}/index.html"))
    finally:
        b.close()
        httpd.shutdown()
    local = ("file:", "data:", "blob:", "about:", "http://127.0.0.1")
    not_local = [u for u in b.requests if not u.startswith(local)]
    OUT.joinpath("layout.json").write_text(json.dumps(layout, indent=1))
    OUT.joinpath("console.json").write_text(json.dumps(b.console, indent=1))
    OUT.joinpath("network.json").write_text(json.dumps(b.requests, indent=1))
    OUT.joinpath("seek.json").write_text(json.dumps(seeks, indent=1))
    screens = {k: v for k, v in layout.items() if isinstance(v, dict) and "overlaps" in v}
    summary = {"seconds": round(time.time() - t0, 1), "screens": len(list(SHOTS.glob("*.png"))),
               "console_errors": len(b.console), "requests_off_the_machine": not_local,
               "short_last_lines": {k: v["short_last_lines"] for k, v in screens.items() if v["short_last_lines"]},
               "overlaps": {k: v["overlaps"] for k, v in screens.items() if v["overlaps"]},
               "spills": {k: v["spills"] for k, v in screens.items() if v.get("spills")},
               "wider_than_window": [k for k, v in screens.items() if v["wider_than_window"]],
               "tabs_on_one_line": {k: v for k, v in layout.items() if k.startswith("tabs_one_line")},
               "threads": {k: v for k, v in layout.items() if k.startswith("threads-")},
               "replay_ended": layout.get("replay_ended"),
               "seek": seeks}
    OUT.joinpath("browser_check.json").write_text(json.dumps(summary, indent=1))
    shown = {k: (len(v) if k in ("short_last_lines", "overlaps", "spills") else v) for k, v in summary.items()
             if k != "seek"}
    shown["threads"] = {"shots": len(summary["threads"]),
                        "broken_paths": sum(v.get("bad", 0) for v in summary["threads"].values() if v),
                        "shots_without_threads": [k for k, v in summary["threads"].items() if not (v or {}).get("threads")]}
    print(json.dumps(shown, indent=1))
    print("Seek test: " + "; ".join(f"{s['url'].split(':')[0]} {'passes' if s['passes'] else 'FAILS'} on the {s['timed_by']}"
                                    for s in seeks))
    print(f"Screenshots are in {SHOTS}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
