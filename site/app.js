/* Call Companion. The page script for the workspace: the calls on the left, the call in the middle, and what it
   produced on the right, with a thread drawn from each item to the line it came from. Everything comes from
   window.CC, which the build wrote, so nothing reaches the network except the call's own audio file. Events are
   handled once at the document. Positions and widths go through the CSSOM from data attributes and are never written
   inline, which keeps the page inside its content security policy. Pure helpers sit on window.CCP for the node
   check. */
(function () {
  "use strict";
  var win = window, doc = document, CC = win.CC || {}, U = CC.ui || {};
  var CCP = win.CCP = {};
  /* A touch screen without a mouse, which is a phone or a tablet. Its copy names taps, not pointing or keys. */
  var TOUCH = !!(win.matchMedia && win.matchMedia("(hover: none) and (pointer: coarse)").matches);
  var checker = win.CCClaims ? win.CCClaims.make(CC.lexicon) : null;
  var CALLS = {}, FIELDS = U.fields || {}, DEAL = CC.deal || [];
  (CC.calls || []).forEach(function (c) {
    CALLS[c.id] = c;
    c.segIndex = {};
    c.segs.forEach(function (g, i) { c.segIndex[g.id] = i; });
    c.side = {};
    c.people.forEach(function (p) { c.side[p.code] = p.side; });
  });
  var MEDDPICC = ["metrics", "economic_buyer", "decision_criteria", "decision_process", "paper_process", "pain",
    "champion", "competition"];
  var OTHER = ["critical_event", "budget", "pricing", "amount", "close_date", "next_steps", "stakeholders", "risks",
    "account", "seller_claims", "commitments"];
  var FLAGS = ["concession", "pain", "critical_event", "amount", "close_date", "budget", "competition", "metrics",
    "decision_criteria", "economic_buyer", "next_steps"];
  var PANELS = ["fields", "deal", "email", "coach"];
  var MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
    "November", "December"];
  var WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  var NUMBERS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
    "twelve"];
  var ALPHA = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
  var weights = {};
  Object.keys((CC.rubric || {}).components || {}).forEach(function (k) { weights[k] = CC.rubric.components[k].weight; });
  var S = {panel: "fields", view: "work", call: DEAL[0] || ((CC.calls || [{}])[0] || {}).id,
    model: CC.route || ((CC.models || [])[0] || {}).id, cutoff: 0.7, follow: true, t: 0, playing: false, rate: 1,
    off: {}, approved: false, editing: false, text: null, search: "", present: 0, codeFile: null, userScroll: 0,
    nowSeg: -1, replay: false, heard: -1, stageNow: "", bodyScroll: 0, screen: "call"};
  var P = {audio: null, url: null, call: null, clock: 0, timer: 0, loading: false};
  var T = {hot: null, row: null, queued: false, animate: false, started: false, anim: [], linkD: "", linkY: null,
    slide: false, fill: false};
  var R = {key: "", raw: null, view: null};
  var STEPS = [];

  /* ------------------------------------------------------------------ helpers */
  function esc(s) {
    return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"}[c];
    });
  }
  function $(sel, root) { return (root || doc).querySelector(sel); }
  function $$(sel, root) { return root === null ? [] : Array.prototype.slice.call((root || doc).querySelectorAll(sel)); }
  function word(key, fill) {
    var s = U[key];
    if (s === undefined) { s = ""; }
    Object.keys(fill || {}).forEach(function (k) { s = String(s).split("{" + k + "}").join(fill[k]); });
    return s;
  }
  /* A sentence from WORDS.md with one marked-up piece in it, escaped everywhere else. */
  function wordHtml(key, name, html, fill) {
    var f = Object.assign({}, fill || {});
    f[name] = "\u0001";
    return esc(word(key, f)).split("\u0001").join(html);
  }
  function cap(s) { s = String(s || ""); return s.charAt(0).toUpperCase() + s.slice(1); }
  function fmtTime(t) {
    t = Math.max(0, Math.floor(t || 0));
    return Math.floor(t / 60) + ":" + String(t % 60).padStart(2, "0");
  }
  function pct(x) { return x === null || x === undefined ? "" : Math.round(x * 100) + "%"; }
  function f1(x) { return String(Math.round(x * 10) / 10); }
  function numberWord(n) { return NUMBERS[n] || String(n); }
  function joinNames(list) {
    list = (list || []).filter(Boolean);
    if (list.length < 2) { return list[0] || ""; }
    if (list.length === 2) { return list[0] + " and " + list[1]; }
    return list.slice(0, -1).join(", ") + ", and " + list[list.length - 1];
  }
  function call() { return CALLS[S.call]; }
  function rawAi(c, m) {
    c = c || call();
    return c.ai[m || S.model] || c.ai[CC.route] || c.ai[Object.keys(c.ai)[0]] || null;
  }
  /* A call's recorded run as the page shows it. During a replay the open call shows only what had been said by the
     playhead, and every panel draws from that view. */
  function ai(c, m) {
    c = c || call();
    var a = rawAi(c, m);
    return a && live(c) ? heardView(c, a) : a;
  }

  /* ------------------------------------------------------------------ the replay */
  function live(c) { return !!(S.replay && c && c.id === S.call); }
  /* The second a fact counts as said: where its first quote ends in its line. The build credits a stage move by the
     same rule (said_at in app/bundle.py), so the change list and the staircase agree with the replay. */
  function factAt(c, f) {
    if (f._at !== undefined) { return f._at; }
    var e = f.ev && f.ev[0], i = e ? c.segIndex[e[0]] : undefined, at = 0;
    if (i !== undefined) {
      var g = c.segs[i], q = e[1] || "", k = q ? g.text.indexOf(q) : -1;
      at = g.s + (g.e - g.s) * Math.min(1, k >= 0 ? (k + q.length) / Math.max(1, g.text.length) : 1);
    }
    f._at = at;
    return at;
  }
  CCP.factAt = function (callId, factId) {
    var c = CALLS[callId], a = c ? rawAi(c) : null, f = a ? a.facts.filter(function (x) { return x.id === factId; })[0] : null;
    return f ? factAt(c, f) : null;
  };
  function heardCount(c, a) {
    var n = 0;
    a.facts.forEach(function (f) { if (factAt(c, f) <= S.t) { n += 1; } });
    return n;
  }
  /* The run as of the playhead. Checks and fields this call met count once their fact is said, and a field this call
     hasn't set yet shows what the last call left. The email and the coaching note wait for the end of the call. */
  function heardView(c, a) {
    var n = heardCount(c, a), key = c.id + "|" + S.model + "|" + S.approved + "|" + n;
    if (R.key === key && R.raw === a) { return R.view; }
    var ids = {}, at = DEAL.indexOf(c.id), before = at > 0 ? rawAi(CALLS[DEAL[at - 1]]) : null;
    var prev = before && before.crm ? before.crm : {};
    a.facts.forEach(function (f) { if (factAt(c, f) <= S.t) { ids[f.id] = true; } });
    function has(callId, id) { return callId !== c.id || !id || !!ids[id]; }
    function rec(r, last) {
      if (!r) { return r; }
      var fields = {};
      Object.keys(r.fields).forEach(function (k) {
        var v = r.fields[k];
        if (Array.isArray(v)) {
          fields[k] = v.filter(function (e) { return Array.isArray(e) ? !!e[2] || has(e[1], e[0]) : has(e.call, e.fact); });
        } else if (v && typeof v === "object" && v.fact) {
          fields[k] = has(v.call, v.fact) ? v : (last && last.fields[k]) || null;
        } else { fields[k] = v; }
      });
      return Object.assign({}, r, {fields: fields, payload: null, checks: r.checks.map(function (x) {
        return x[1] && !has(x[3], x[2]) ? [x[0], false, null, null] : x;
      })});
    }
    var crm = a.crm ? Object.assign({}, a.crm, {
      record: rec(a.crm.record, prev.record),
      approved: rec(a.crm.approved, prev.approved || prev.record),
      changes: a.crm.changes ? a.crm.changes.filter(function (ch) { return has(ch.call, ch.fact); }) : a.crm.changes,
      concessions: (a.crm.concessions || []).filter(function (id) { return !!ids[id]; })}) : a.crm;
    var view = Object.assign({}, a, {facts: a.facts.filter(function (f) { return !!ids[f.id]; }), held: [], email: null,
      emailApproved: null, coach: null, crm: crm, concessions: (a.concessions || []).filter(function (id) { return !!ids[id]; })});
    R = {key: key, raw: a, view: view};
    return view;
  }
  function modelLabel(m) {
    var x = (CC.models || []).filter(function (y) { return y.id === (m || S.model); })[0];
    return x ? x.label : m;
  }
  function person(c, code) { return c.people.filter(function (p) { return p.code === code; })[0] || {name: code}; }
  function factIn(callId, id) {
    var a = CALLS[callId] ? ai(CALLS[callId]) : null;
    return a ? a.facts.filter(function (f) { return f.id === id; })[0] || null : null;
  }
  function segAt(c, t) {
    var lo = 0, hi = c.segs.length - 1, best = -1;
    while (lo <= hi) {
      var mid = (lo + hi) >> 1;
      if (c.segs[mid].s <= t) { best = mid; lo = mid + 1; } else { hi = mid - 1; }
    }
    return best;
  }
  function segTime(c, segId) { var i = c.segIndex[segId]; return i === undefined ? null : c.segs[i].s; }
  function calm() { return !!(win.matchMedia && win.matchMedia("(prefers-reduced-motion: reduce)").matches); }
  function raf(fn) { return (win.requestAnimationFrame || function (f) { return win.setTimeout(f, 16); })(fn); }
  CCP.fmtTime = fmtTime;
  CCP.segAt = segAt;

  /* Dates arrive as ISO days and are read in UTC, so a reader's time zone never shifts them. */
  function ymd(iso) {
    var p = String(iso).split("-");
    return {y: parseInt(p[0], 10), m: parseInt(p[1], 10), d: parseInt(p[2], 10)};
  }
  function dayNum(iso) { var p = ymd(iso); return Date.UTC(p.y, p.m - 1, p.d) / 86400000; }
  function weekday(iso) { var p = ymd(iso); return new Date(Date.UTC(p.y, p.m - 1, p.d)).getUTCDay(); }
  function dayLabel(iso) { var p = ymd(iso); return MONTHS[p.m - 1] + " " + p.d + ", " + p.y; }
  function longDay(iso) { var p = ymd(iso); return WEEKDAYS[weekday(iso)] + ", " + MONTHS[p.m - 1] + " " + p.d; }
  function shortDay(iso) {
    var p = ymd(iso);
    return WEEKDAYS[weekday(iso)].slice(0, 3) + ", " + MONTHS[p.m - 1].slice(0, 3) + " " + p.d;
  }
  function monthDay(iso) { var p = ymd(iso); return MONTHS[p.m - 1].slice(0, 3) + " " + p.d; }
  function fullMonthDay(iso) { var p = ymd(iso); return MONTHS[p.m - 1] + " " + p.d; }

  /* A chip that plays a moment: the first evidence segment of a fact, in the call it came from. */
  function chip(callId, segId, label) {
    var c = CALLS[callId], i = c ? c.segIndex[segId] : undefined;
    if (i === undefined) { return ""; }
    var g = c.segs[i];
    return "<button type='button' class='chip " + esc(c.side[g.sp] || "") + "' data-call='" + esc(callId) +
      "' data-seg='" + esc(segId) + "' title='" + esc(word("chip.play")) + "'>" + esc(label || fmtTime(g.s)) +
      "</button>";
  }
  /* One chip per line. A fact can quote two phrases from the same line, and two chips with one time read as a slip. */
  function factChips(callId, f) {
    if (!f) { return ""; }
    var seen = {};
    return "<span class='chips'>" + (f.ev || []).filter(function (e) {
      var fresh = !seen[e[0]];
      seen[e[0]] = true;
      return fresh;
    }).map(function (e) { return chip(callId, e[0]); }).join("") + "</span>";
  }
  /* The attribute that gives an item its thread: its first evidence line, when that line is in the open call. */
  function evAttr(callId, f) {
    return f && callId === S.call && f.ev && f.ev.length ? " data-ev='" + esc(f.ev[0][0]) + "'" : "";
  }
  function place(root) {
    $$("[data-left]", root).forEach(function (el) { el.style.left = el.getAttribute("data-left") + "%"; });
    $$("[data-width]", root).forEach(function (el) { el.style.width = el.getAttribute("data-width") + "%"; });
    $$("[data-grow]", root).forEach(function (el) { el.style.flexGrow = el.getAttribute("data-grow"); });
  }
  function callName(id) {
    var c = CALLS[id];
    if (!c) { return id; }
    var i = DEAL.indexOf(id);
    return i >= 0 ? "call " + (i + 1) : c.title;
  }
  function peopleLine(c) {
    var rep = person(c, c.rep);
    var others = c.people.filter(function (p) { return p.code !== c.rep; }).map(function (p) { return p.name; });
    return word("call.people", {rep: rep.name, others: joinNames(others)});
  }
  function sideNames(list) {
    return list.length === 1 ? list[0].name : joinNames(list.map(function (p) { return p.name.split(" ")[0]; }));
  }

  /* ------------------------------------------------------------------ the waveforms */
  function levels(str) {
    var out = [];
    for (var i = 0; i < str.length; i++) { out.push(Math.max(0, ALPHA.indexOf(str.charAt(i))) / 61); }
    return out;
  }
  function buckets(lv, n) {
    var out = [], size = lv.length;
    for (var i = 0; i < n; i++) {
      var a = Math.floor(i * size / n), b = Math.max(a + 1, Math.floor((i + 1) * size / n)), top = 0;
      for (var k = a; k < b && k < size; k++) { if (lv[k] > top) { top = lv[k]; } }
      out.push(top);
    }
    return out;
  }
  /* One waveform for the whole call: the seller's tracks above the line and the buyer's below it. */
  function wave(c, n, h, pad, cls) {
    var key = "_w" + n + "x" + h + cls;
    if (c[key]) { return c[key]; }
    var up = [], down = [], i;
    for (i = 0; i < n; i++) { up.push(0); down.push(0); }
    Object.keys(c.peaks || {}).forEach(function (code) {
      var b = buckets(levels(c.peaks[code] || ""), n), target = c.side[code] === "seller" ? up : down;
      for (var j = 0; j < n; j++) { if (b[j] > target[j]) { target[j] = b[j]; } }
    });
    var mid = h / 2, top = "", bottom = "";
    for (i = 0; i < n; i++) {
      if (up[i] > 0) {
        var uh = Math.max(1.5, up[i] * (mid - pad));
        top += "M" + i * 3 + " " + f1(mid - 1 - uh) + "h2v" + f1(uh) + "h-2z";
      }
      if (down[i] > 0) {
        var dh = Math.max(1.5, down[i] * (mid - pad));
        bottom += "M" + i * 3 + " " + f1(mid + 1) + "h2v" + f1(dh) + "h-2z";
      }
    }
    c[key] = "<svg class='" + cls + "' viewBox='0 0 " + n * 3 + " " + h + "' preserveAspectRatio='none' " +
      "aria-hidden='true'><path class='up' d='" + (top || "M0 0") + "'/><path class='down' d='" + (bottom || "M0 0") +
      "'/></svg>";
    return c[key];
  }

  /* ------------------------------------------------------------------ the address */
  function writeHash() {
    if (!win.history || !win.history.replaceState) { return; }
    var h = S.present ? "#present-" + S.present : S.view === "how" ? "#how" : "#" + S.panel + "/" + S.call;
    try { win.history.replaceState(null, "", h); } catch (e) { /* file:// in some browsers */ }
  }
  function readHash(h) {
    var m = /^#present-(\d+)$/.exec(h || "");
    if (m) { return {present: Math.min(STEPS.length || 12, Math.max(1, parseInt(m[1], 10)))}; }
    if (h === "#how") { return {how: true}; }
    m = /^#(fields|deal|email|coach|call)(?:\/([a-z0-9-]+))?$/.exec(h || "");
    return m ? {panel: m[1] === "call" ? "fields" : m[1], call: m[2]} : {};
  }
  CCP.readHash = readHash;

  /* ------------------------------------------------------------------ the player */
  function length() { return call().length; }
  function now() { return P.audio && !P.audio.paused ? P.audio.currentTime : S.t; }
  function ensureAudio(c, then) {
    if (!c.audio || typeof Audio === "undefined") { then(false); return; }
    if (P.audio && P.call === c.id) { then(true); return; }
    if (P.url && win.URL) { win.URL.revokeObjectURL(P.url); }
    P.audio = new Audio(); P.call = c.id; P.url = null;
    P.audio.preload = "metadata";
    if (win.location.protocol === "file:" || !win.fetch) { P.audio.src = c.audio; then(true); return; }
    P.loading = true;
    renderClock();
    win.fetch(c.audio).then(function (r) { return r.blob(); }).then(function (b) {
      P.url = win.URL.createObjectURL(b);
      P.audio.src = P.url;
      P.loading = false;
      then(true);
    }).catch(function () { P.loading = false; P.audio.src = c.audio; then(true); });
  }
  function hasAudio() { return !!(P.audio && P.call === S.call); }
  /* The audio plays at 1× to 2×. Faster than that the page's own clock keeps time and the call runs silent. */
  function audible() { return hasAudio() && S.rate <= 2; }
  function play() {
    var c = call();
    if (S.t >= length() - 0.05) { S.t = 0; }
    ensureAudio(c, function (has) {
      S.playing = true;
      if (has && S.rate <= 2) {
        P.audio.currentTime = S.t;
        P.audio.playbackRate = S.rate;
        var pr = P.audio.play();
        if (pr && pr.catch) { pr.catch(function () { S.playing = false; renderClock(); }); }
      } else {
        P.clock = Date.now() - S.t * 1000 / S.rate;
      }
      renderClock();
      loop();
    });
  }
  function pause() {
    if (P.audio && !P.audio.paused) { S.t = P.audio.currentTime; P.audio.pause(); }
    S.playing = false;
    renderClock();
  }
  function seek(t, andPlay) {
    S.t = Math.max(0, Math.min(length(), t));
    if (hasAudio()) { P.audio.currentTime = S.t; }
    P.clock = Date.now() - S.t * 1000 / S.rate;
    S.userScroll = 0;
    onTime(true);
    if (andPlay && !S.playing) { play(); }
  }
  function setRate(r) {
    var was = audible();
    if (was && !P.audio.paused) { S.t = P.audio.currentTime; }
    S.rate = r > 0 ? r : 1;
    if (P.audio) { P.audio.playbackRate = Math.min(S.rate, 2); }
    P.clock = Date.now() - S.t * 1000 / S.rate;
    if (S.playing && hasAudio() && was !== audible()) {
      if (was) { P.audio.pause(); }
      else {
        P.audio.currentTime = S.t;
        var pr = P.audio.play();
        if (pr && pr.catch) { pr.catch(function () {}); }
      }
    }
    renderClock();
  }
  function loop() {
    if (!S.playing) { return; }
    if (audible()) {
      S.t = P.audio.currentTime;
      if (P.audio.ended) { S.playing = false; }
    } else {
      S.t = (Date.now() - P.clock) * S.rate / 1000;
      if (S.t >= length()) { S.t = length(); S.playing = false; }
    }
    onTime(false);
    if (!S.playing) { renderClock(); return; }
    P.timer = raf(loop);
  }
  function onTime(force) {
    var c = call(), head = $("#playhead");
    if (head) { head.style.left = (S.t / length() * 100).toFixed(3) + "%"; }
    var scrub = $("#scrub");
    if (scrub && doc.activeElement !== scrub) { scrub.value = String(Math.round(S.t * 10)); }
    var clock = $("#clock");
    if (clock) { clock.textContent = fmtTime(S.t) + " / " + fmtTime(length()); }
    var i = segAt(c, S.t + 0.05);
    if (i !== S.nowSeg || force) {
      var old = $("#rows .now");
      if (old) { old.classList.remove("now"); }
      var el = doc.getElementById("seg-" + i);
      if (el) {
        el.classList.add("now");
        if (S.follow && Date.now() - S.userScroll > 4000 && (S.playing || S.t > 0)) { scrollRow(el, 0.3, false); }
      }
      S.nowSeg = i;
    }
    if (S.replay) { replayTick(); }
  }
  function renderClock() {
    var b = $("#play");
    if (b) {
      b.setAttribute("aria-label", S.playing ? word("player.pause") : word("player.play"));
      b.innerHTML = S.playing ? "<svg viewBox='0 0 16 16'><rect x='3' y='2' width='3.5' height='12'/><rect x='9.5' y='2' " +
        "width='3.5' height='12'/></svg>" : "<svg viewBox='0 0 16 16'><path d='M4 2l10 6-10 6z'/></svg>";
    }
    var note = $("#player-note");
    if (note) {
      note.textContent = P.loading ? word("player.loading") : !call().audio ? word("player.noaudio") :
        S.rate > 2 ? word("player.silent") : TOUCH ? "" : word("player.hint");
    }
  }
  /* How much of the top of the transcript its sticky header covers. Lines under it are out of sight. */
  function headUnder() {
    var head = $("#transcript .pane-head");
    return head && typeof head.offsetHeight === "number" ? head.offsetHeight : 0;
  }
  /* Scrolls the transcript so a line sits a set share of the way down the part below the header. Only the transcript
     moves. */
  function scrollRow(el, where, smooth) {
    var pane = $("#transcript");
    if (!pane || !el) { return; }
    if (typeof el.offsetTop === "number" && pane.clientHeight) {
      var under = headUnder(), to = Math.max(0, el.offsetTop - under - (pane.clientHeight - under) * where);
      if (pane.scrollTo) { pane.scrollTo({top: to, behavior: smooth && !calm() ? "smooth" : "auto"}); }
      else { pane.scrollTop = to; }
    } else if (el.scrollIntoView) { el.scrollIntoView({block: "nearest"}); }
  }
  function seekSeg(segId, andPlay) {
    var c = call(), i = c.segIndex[segId];
    if (i !== undefined) { seek(c.segs[i].s, andPlay); }
  }

  /* ------------------------------------------------------------------ the record and the stage */
  function stageOf(checks, off) {
    var stages = CC.crm.stages, reached = stages[0].name, met = {};
    checks.forEach(function (c) { met[c[0]] = c[1]; });
    for (var i = 0; i < stages.length; i++) {
      var ok = stages[i].rules.every(function (r) { return met[r.id] || off[r.id]; });
      if (!ok) { break; }
      reached = stages[i].name;
    }
    return reached;
  }
  CCP.stageOf = stageOf;
  function recordOf(id, whole) {
    var a = CALLS[id] ? (whole ? rawAi(CALLS[id]) : ai(CALLS[id])) : null, crm = a && a.crm;
    if (!crm) { return null; }
    return S.approved && crm.approved ? crm.approved : crm.record;
  }
  function stageAfter(id) {
    var r = recordOf(id);
    return r ? stageOf(r.checks, S.off) : CC.crm.stages[0].name;
  }
  function dealView(c, a) {
    var crm = a && a.crm;
    if (!crm) { return null; }
    var rec = S.approved && crm.approved ? crm.approved : crm.record;
    return {crm: crm, rec: rec, stage: stageOf(rec.checks, S.off)};
  }
  CCP.stageAfter = stageAfter;

  /* ------------------------------------------------------------------ the left card */
  function renderCalls() {
    var box = $("#call-list");
    if (!box) { return; }
    var names = CC.crm.stages.map(function (s) { return s.name; });
    var first = CALLS[DEAL[0]], last = CALLS[DEAL[DEAL.length - 1]];
    var head = first ? "<div class='pane-top'><p class='eyebrow'>" + esc(word("deal.eyebrow")) + "</p><h2>" +
      esc((first.companies || [])[1] || first.title) + "</h2><p class='sub'>" + esc(word("deal.sub", {
        n: cap(numberWord(DEAL.length)), first: fullMonthDay(first.date), last: fullMonthDay(last.date)})) + "</p></div>" : "";
    var cards = DEAL.map(function (id, i) {
      var c = CALLS[id], st = stageAfter(id), at = names.indexOf(st), on = id === S.call;
      var met = c.people.filter(function (p) { return p.side === "buyer"; }).map(function (p) { return p.name.split(" ")[0]; });
      var path = names.map(function (s, j) { return "<i class='" + (j < at ? "done" : j === at ? "at" : "") + "'></i>"; }).join("");
      return "<button type='button' class='callcard" + (on ? " on" : "") + "' data-pick='" + esc(id) + "' aria-pressed='" +
        (on ? "true" : "false") + "'><span class='num'>" + (i + 1) + "</span><span class='body'><span class='row1'><strong>" +
        esc(c.title) + "</strong><span class='len'>" + fmtTime(c.length) + "</span></span><span class='row2'>" +
        esc(shortDay(c.date)) + " · " + esc(word("call.with", {names: joinNames(met)})) + "</span><span class='wave'>" +
        wave(c, 130, 30, 1.5, "mini-svg") + "</span><span class='row3'><span class='path' title='" + esc(st) + "'>" + path +
        "</span><span class='reached'>" + wordHtml("call.reached", "stage", "<b>" + esc(st) + "</b>") + "</span></span></span></button>";
    }).join("");
    var scored = (CC.calls || []).filter(function (c) { return DEAL.indexOf(c.id) < 0; });
    var tests = scored.filter(function (c) { return c.split === "test"; }).length;
    var rows = scored.map(function (c, i) {
      var on = c.id === S.call;
      return "<button type='button' class='callrow" + (on ? " on" : "") + "' data-pick='" + esc(c.id) + "' aria-pressed='" +
        (on ? "true" : "false") + "' title='" + esc(c.title) + "'><span class='mini-code'>" + (i + 1) + "</span><span class='body'>" +
        "<span class='row1'><strong>" + esc(c.title) + "</strong><span class='len'>" + fmtTime(c.length) + "</span></span>" +
        "<span class='row2'>" + esc(shortDay(c.date)) + " <span class='split " + esc(c.split) + "'>" +
        esc((U.split || {})[c.split] || c.split) + "</span></span></span></button>";
    }).join("");
    var tail = scored.length ? "<div class='pane-top scored'><p class='eyebrow'>" + esc(word("scored.eyebrow")) + "</p><p class='sub'>" +
      esc(word("scored.sub", {n: cap(numberWord(scored.length)), m: cap(numberWord(tests))})) + "</p></div><div class='scoredlist'>" +
      rows + "</div>" : "";
    box.innerHTML = head + "<div class='callcards'>" + cards + "</div>" + tail;
  }

  /* ------------------------------------------------------------------ the middle card */
  function flagsOf(c, a) {
    if (!a) { return []; }
    var labels = U.flags || {}, cands = [], L = c.length || 1;
    FLAGS.forEach(function (field) {
      var f = null;
      if (field === "concession") {
        var id = (a.concessions || [])[0];
        f = id ? a.facts.filter(function (x) { return x.id === id; })[0] : null;
      } else {
        f = a.facts.filter(function (x) { return x.field === field && x.ev && x.ev.length; })[0];
      }
      var t = f && f.ev && f.ev.length ? segTime(c, f.ev[0][0]) : null;
      if (t !== null) { cands.push({label: labels[field] || FIELDS[field] || field, pos: t / L * 100}); }
    });
    var picked = [];
    cands.forEach(function (x) {
      if (picked.length < 5 && picked.every(function (p) { return Math.abs(p.pos - x.pos) >= 9; })) { picked.push(x); }
    });
    return picked.sort(function (x, y) { return x.pos - y.pos; });
  }
  CCP.flagsOf = function (callId) { var c = CALLS[callId]; return flagsOf(c, ai(c)); };
  function scopeHtml(c, a) {
    var L = c.length || 1, seen = {}, ticks = "", ruler = "";
    var flags = flagsOf(c, a).map(function (f, k) {
      return "<span class='flag" + (f.pos > 80 ? " end" : "") + (k % 2 ? " up" : "") + "' data-left='" + f.pos.toFixed(2) + "'>" +
        esc(f.label) + "</span>";
    }).join("");
    (a ? a.facts : []).forEach(function (f) {
      var t = f.ev && f.ev.length ? segTime(c, f.ev[0][0]) : null;
      if (t === null || seen[t]) { return; }
      seen[t] = 1;
      ticks += "<b data-left='" + (t / L * 100).toFixed(2) + "'></b>";
    });
    for (var m = 0; m * 60 <= L; m++) {
      var pos = m * 60 / L * 100;
      ruler += "<span class='" + (m === 0 ? "first" : pos > 92 ? "last" : "") + "' data-left='" + pos.toFixed(2) + "'>" + m +
        ":00</span>";
    }
    return "<div class='scope' id='scope'><div class='flags'>" + flags + "</div><div class='scope-plot'>" +
      wave(c, 260, 112, 5, "scope-svg") + "<div class='ticks'>" + ticks + "</div><div class='hits' id='hits'></div>" +
      "<div class='playhead' id='playhead'></div><input type='range' class='scrub' id='scrub' min='0' max='" + Math.round(L * 10) +
      "' step='1' value='" + Math.round(S.t * 10) + "' aria-label='" + esc(word("player.position")) + "'></div><div class='ruler'>" +
      ruler + "</div></div>";
  }
  function transcriptHtml(c) {
    return c.segs.map(function (g, i) {
      var p = person(c, g.sp);
      var words = g.w.map(function (x) {
        var t = esc(x[0]);
        return x[1] !== null && x[1] < S.cutoff ? "<span class='unsure'>" + t + "</span>" : t;
      }).join(" ");
      return "<div class='seg " + esc(c.side[g.sp]) + "' id='seg-" + i + "' data-i='" + i + "' data-seg='" + esc(g.id) + "'>" +
        "<span class='time'>" + fmtTime(g.s) + "</span><span><span class='sp'>" + esc(p.name) + "</span> <span class='tx'>" +
        words + "</span></span></div>";
    }).join("");
  }
  function renderCall() {
    var c = call(), a = rawAi(c), box = $("#call");
    if (!box || !c) { return; }
    var sellers = c.people.filter(function (p) { return p.side === "seller"; });
    var buyers = c.people.filter(function (p) { return p.side === "buyer"; });
    var legend = "<div class='legend2'>" + (sellers.length ? "<span><i class='s'></i><b>" + esc(sideNames(sellers)) + "</b> " +
      esc(sellers[0].company) + "</span>" : "") + (buyers.length ? "<span><i class='b'></i><b>" + esc(sideNames(buyers)) + "</b> " +
      esc(buyers[0].company) + "</span>" : "") + "</div>";
    var speeds = [1, 1.5, 2, 4, 8].map(function (r) {
      return "<option value='" + r + "'" + (S.rate === r ? " selected" : "") + ">" + r + "×</option>";
    }).join("");
    var deck = "<div class='deck'><div class='deck-title'><h1 id='call-title'>" + esc(c.title) + "</h1><p class='meta'>" +
      esc(longDay(c.date)) + " · " + esc(peopleLine(c)) + "</p></div><div class='deck-controls'><button type='button' " +
      "class='play' id='play'></button><span class='clock' id='clock'></span><label class='speed'><span class='sr'>" +
      esc(word("player.speed")) + "</span><select id='speed'>" + speeds + "</select></label><button type='button' class='btn small replay" +
      (S.replay ? " on" : "") + "' id='replay' aria-pressed='" + (S.replay ? "true" : "false") + "'>" +
      esc(word(S.replay ? "replay.all" : "replay.start")) + "</button>" + legend + "</div>" +
      scopeHtml(c, a) + "<p class='player-note' id='player-note'></p></div>";
    var trans = "<div class='transcript-pane' id='transcript'><div class='pane-head'><div class='pane-row'><h3>" +
      esc(word("transcript.title")) + "</h3><div class='pane-tools'><input type='search' class='search' id='search' " +
      "placeholder='" + esc(word("search.placeholder")) + "' value='" + esc(S.search) + "'><span class='search-count' " +
      "id='search-count'></span><label class='follow'><input type='checkbox' id='follow'" + (S.follow ? " checked" : "") + ">" +
      esc(word("transcript.follow")) + "</label></div></div><div class='cutoff'><label for='cutoff'>" +
      esc(word("transcript.cutoff", {p: Math.round(S.cutoff * 100)})) + "</label><input type='range' id='cutoff' min='50' " +
      "max='99' value='" + Math.round(S.cutoff * 100) + "'><span class='confirm-count' id='confirm-count'></span></div></div>" +
      "<div class='rows' id='rows'>" + transcriptHtml(c) + "</div></div>";
    box.innerHTML = deck + trans;
    place(box);
    renderClock();
    markSearch();
    confirmCount();
    S.nowSeg = -1;
    onTime(true);
  }
  function confirmCount() {
    var a = ai(), el = $("#confirm-count");
    if (!el || !a) { return; }
    var n = a.facts.filter(function (f) { return f.conf < S.cutoff; }).length;
    el.textContent = n ? word(n === 1 ? "confirm.one" : "confirm.count", {n: n}) : word("confirm.none");
  }
  function markSearch() {
    var c = call(), q = S.search.trim().toLowerCase(), hits = $("#hits"), count = $("#search-count");
    if (!hits) { return; }
    var found = [];
    if (q.length > 1) {
      c.segs.forEach(function (g, i) { if (g.text.toLowerCase().indexOf(q) >= 0) { found.push(i); } });
    }
    hits.innerHTML = found.map(function (i) {
      return "<b data-left='" + (c.segs[i].s / c.length * 100).toFixed(2) + "'></b>";
    }).join("");
    place(hits);
    $$("#rows .seg").forEach(function (el) {
      var i = parseInt(el.getAttribute("data-i"), 10), tx = $(".tx", el), g = c.segs[i];
      if (!tx) { return; }
      var html = g.w.map(function (x) {
        var t = esc(x[0]);
        return x[1] !== null && x[1] < S.cutoff ? "<span class='unsure'>" + t + "</span>" : t;
      }).join(" ");
      if (found.indexOf(i) >= 0) {
        var re = new RegExp("(" + q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/&/g, "&amp;") + ")", "ig");
        html = html.replace(/(<[^>]*>)|([^<]+)/g, function (m, tag, text) { return tag || text.replace(re, "<mark>$1</mark>"); });
      }
      tx.innerHTML = html;
    });
    if (count) { count.textContent = q.length > 1 ? (found.length ? word("search.count", {n: found.length}) : word("search.none")) : ""; }
    CCP.lastSearch = found.length;
  }

  /* ------------------------------------------------------------------ the right card */
  /* Redraws the open panel. keep holds the scroll place, and landing marks what wasn't there before so it lands with a
     highlight and only its thread draws in. */
  function renderPanel(animate, keep, landing) {
    var c = call(), a = ai(c), body = $("#record-body");
    if (!body) { return; }
    $$("[data-panel-tab]").forEach(function (b) {
      var on = b.getAttribute("data-panel-tab") === S.panel;
      b.setAttribute("aria-selected", on ? "true" : "false");
      b.setAttribute("tabindex", on ? "0" : "-1");
      b.classList.toggle("on", on);
    });
    var count = $("#count-fields");
    if (count) { count.textContent = a ? String(a.facts.length) : ""; }
    var was = stairState(), seen = landing ? keysIn(body) : null;
    var html = S.panel === "deal" ? dealHtml(c, a) : S.panel === "email" ? emailHtml(c, a) :
      S.panel === "coach" ? coachHtml(c, a) : fieldsHtml(c, a);
    var top = body.scrollTop;
    body.innerHTML = "<div class='panel-in' id='p-" + S.panel + "'>" + (live(c) ? replayNote() : "") + html + "</div>";
    place(body);
    if (typeof body.scrollTop === "number") { body.scrollTop = keep ? top : 0; }
    stairMotion(was);
    var first = seen ? markLanding(body, seen) : null;
    if (T.fill) { fillIn(body); }
    writeHash();
    soonThreads(animate ? true : landing ? "new" : false);
    if (first && live(c)) { bringIn(first); }
  }
  function fieldsHtml(c, a) {
    if (!a) { return "<p class='empty'>" + esc(word("facts.empty")) + "</p>"; }
    function field(name) {
      var items = a.facts.filter(function (f) { return f.field === name; });
      var body = items.length ? items.map(function (f) {
        var unsure = f.conf < S.cutoff ? "<span class='confirm' title='" + esc(word("confirm.why")) + "'>" +
          esc(word("confirm.tag")) + "</span>" : "";
        return "<div class='fact' data-fact='" + esc(f.id) + "'" + evAttr(c.id, f) + ">" + esc(f.value) + factChips(c.id, f) +
          unsure + "</div>";
      }).join("") : "<p class='empty'>" + esc(word(live(c) ? "replay.notyet" : "facts.empty")) + "</p>";
      return "<div class='field' data-field='" + esc(name) + "'><h4>" + esc(FIELDS[name] || name) +
        (items.length ? "<span class='count'>" + items.length + "</span>" : "") + "</h4>" + body + "</div>";
    }
    var held = a.held.length ? "<div class='held'><h4>" + esc(word("facts.held")) + "</h4><p>" + esc(word("facts.heldnote")) +
      "</p><ul>" + a.held.map(function (h) {
        return "<li><span class='tag'>" + esc(FIELDS[h.field] || h.field) + "</span>" + esc(h.value) + " <span class='muted'>(" +
          esc(h.reasons.join("; ")) + ")</span></li>";
      }).join("") + "</ul></div>" : "";
    return "<p class='byline'>" + esc(word("facts.by", {model: modelLabel()})) + "</p><div class='facts' id='facts'>" +
      MEDDPICC.map(field).join("") + "<details class='more' open><summary>" + esc(word("facts.more")) + "</summary>" +
      OTHER.map(field).join("") + "</details>" + held + "</div>";
  }

  /* The deal panel: the record, the staircase, what this call changed, the stage rules and the rest of the record. */
  function dealHtml(c, a) {
    var v = dealView(c, a);
    if (!v) { return "<p class='empty'>" + esc(word("facts.empty")) + "</p>"; }
    var isDeal = DEAL.indexOf(c.id) >= 0, f = v.rec.fields;
    var amount = f.amount && f.amount.value !== null && f.amount.value !== undefined ?
      "$" + Number(f.amount.value).toLocaleString("en-US") : "";
    var close = f.close_date && f.close_date.value ? shortDay(f.close_date.value) : "";
    function cell(label, val, cls, id) {
      return "<div><dt>" + esc(label) + "</dt><dd" + (id ? " id='" + id + "'" : "") + " class='" + (val ? cls || "" : "none") + "'>" +
        esc(val || word("deal.notyet")) + "</dd></div>";
    }
    var rec = "<dl class='rec' id='deal-rec'>" + cell(word("deal.stage"), v.stage, "rec-stage", "deal-stage-now") +
      cell(FIELDS.amount, amount) + cell(FIELDS.close_date, close) + "</dl>";
    var stair = isDeal ? "<div class='block' id='deal-stair'><div class='block-head'><h3>" + esc(word("stair.title")) +
      "</h3><span>" + esc(word("stair.note")) + "</span></div><div class='stair' id='stair'>" + stairSvg(c.id) + "</div></div>" :
      "<p class='muted single'>" + esc(word("deal.single")) + "</p>";
    var approve = (v.crm.concessions || []).length ? "<div class='approve' id='approve-box'><label><input type='checkbox' " +
      "id='approve'" + (S.approved ? " checked" : "") + ">" + esc(word("deal.approve")) + "</label><p>" +
      esc(word("deal.approvenote")) + "</p></div>" : "";
    return rec + stair + approve + (isDeal ? changesHtml(c, a) : "") + rulesHtml(v) + recordHtml(c, v, isDeal) +
      commitsHtml(v) + (live(c) ? "" : payloadHtml(v));
  }
  function changesHtml(c, a) {
    var kinds = U["deal.kind"] || {}, list = (a.crm && a.crm.changes) || [], n = DEAL.indexOf(c.id) + 1, top = [], rest = [];
    list.forEach(function (ch) { (ch.kind === "fact" || ch.kind === "commitment" ? rest : top).push(ch); });
    function item(kind, label, text, callId, f, extra) {
      return "<li class='chg-" + esc(kind) + "'" + (callId === c.id ? evAttr(c.id, f) : "") + "><span class='kind " + esc(kind) +
        "'>" + esc(label) + "</span><span class='what'>" + esc(cap(text)) + (f ? factChips(callId, f) : "") + (extra || "") +
        "</span></li>";
    }
    function fromChange(ch) {
      var f = ch.fact && ch.call ? factIn(ch.call, ch.fact) : null;
      var at = ch.text.indexOf(": "), text = at >= 0 ? ch.text.slice(at + 2) : ch.text;
      var label = ch.kind === "fact" || ch.kind === "commitment" ? FIELDS[ch.field] || kinds[ch.kind] || ch.kind :
        kinds[ch.kind] || ch.kind;
      var extra = ch.call && ch.call !== c.id ? " <span class='muted'>" + esc(word("deal.from", {call: callName(ch.call)})) +
        "</span>" : "";
      return item(ch.kind, label, text, ch.call, f, extra);
    }
    var waits = (a.concessions || []).map(function (id) {
      var f = factIn(c.id, id), k = S.approved ? "approved" : "wait";
      return f ? item(k, kinds[k] || k, f.value, c.id, f) : "";
    }).join("");
    var main = top.map(fromChange), cut = 0;
    top.forEach(function (ch, i) { if (["stage", "amount", "close_date", "next_step"].indexOf(ch.kind) >= 0) { cut = i + 1; } });
    main.splice(cut, 0, waits);
    var more = rest.length ? "<details class='more'><summary>" + esc(word("deal.more", {n: rest.length})) + "</summary>" +
      "<ul class='chg'>" + rest.map(fromChange).join("") + "</ul></details>" : "";
    return "<div class='block' id='deal-changes'><div class='block-head'><h3>" + esc(word("deal.changed", {n: n})) + "</h3><span>" +
      esc(TOUCH ? word("deal.point.touch") : word("deal.point")) + "</span></div><ul class='chg'>" + main.join("") + "</ul>" + more + "</div>";
  }
  function rulesHtml(v) {
    var met = {};
    v.rec.checks.forEach(function (x) { met[x[0]] = x; });
    var rules = CC.crm.stages.filter(function (s) { return s.rules.length; }).map(function (s) {
      return "<li class='stage-name'>" + esc(s.name) + "</li>" + s.rules.map(function (r) {
        var x = met[r.id] || [r.id, false, null, null], off = !!S.off[r.id];
        var why = x[2] && x[3] ? factChips(x[3], factIn(x[3], x[2])) : "";
        return "<li class='" + (off ? "off" : "") + "'><span class='" + (x[1] ? "ok" : "no") + "'>" + (x[1] ? "✓" : "✗") +
          "</span><span>" + esc(r.label) + why + "</span><label><input type='checkbox' data-rule='" + esc(r.id) + "'" +
          (off ? "" : " checked") + ">" + esc(word("deal.ruleoff")) + "</label></li>";
      }).join("");
    }).join("");
    return "<div class='block' id='deal-stage'><div class='block-head'><h3>" + esc(word("deal.rules")) + "</h3></div>" +
      "<p class='muted note'>" + esc(word("deal.rulesnote")) + "</p><ul class='rules' id='rules'>" + rules + "</ul></div>";
  }
  function factValue(entry) {
    var f = factIn(entry[1], entry[0]);
    if (!f) { return ""; }
    var first = entry[2] ? " <span class='first'>" + esc(word("deal.first", {call: callName(entry[2])})) + "</span>" : "";
    return "<div>" + esc(f.value) + factChips(entry[1], f) + first + "</div>";
  }
  function recordHtml(c, v, isDeal) {
    var fields = CC.crm.fields.map(function (fd) {
      var val = v.rec.fields[fd.key], body;
      if (fd.kind === "stage") { body = "<div><strong>" + esc(v.stage) + "</strong></div>"; }
      else if (fd.kind === "money" || fd.kind === "date" || fd.kind === "next") {
        body = val ? "<div>" + esc(fd.kind === "money" ? "$" + Number(val.value).toLocaleString("en-US") :
          fd.kind === "date" && val.value ? dayLabel(val.value) : val.value || val.text) +
          factChips(val.call, factIn(val.call, val.fact)) + "</div>" : "";
      } else if (fd.kind === "contacts") {
        body = (val || []).map(function (p) {
          return "<div>" + esc(p.name) + (p.title ? ", " + esc(p.title) : "") + " <span class='tag'>" + esc(p.role) + "</span>" +
            factChips(p.call, factIn(p.call, p.fact)) + "</div>";
        }).join("");
      } else { body = (val || []).map(factValue).join(""); }
      return "<dt>" + esc(fd.label) + "<span class='api'>" + esc(fd.api) + "</span></dt><dd>" +
        (body || "<span class='empty'>" + esc(word("deal.empty")) + "</span>") + "</dd>";
    }).join("");
    return "<details class='more block' id='deal-record'><summary>" + esc(word("deal.title", {call: isDeal ? callName(c.id) : c.title})) +
      "</summary><dl class='recfull'>" + fields + "</dl></details>";
  }
  function commitsHtml(v) {
    var commits = (v.rec.fields.commitments || []).map(function (e) {
      var f = factIn(e[1], e[0]);
      return f ? {f: f, call: e[1]} : null;
    }).filter(Boolean);
    function side(name) {
      var mine = commits.filter(function (x) { return (x.f.by || "seller") === name; });
      return mine.length ? "<ul>" + mine.map(function (x) {
        var tag = x.f.kind === "concession" ? "<span class='status-tag " + (S.approved ? "approved" : "waiting") + "'>" +
          esc(S.approved ? word("deal.approved") : word("deal.waiting")) + "</span>" : "";
        return "<li>" + esc(x.f.value) + tag + factChips(x.call, x.f) + "</li>";
      }).join("") + "</ul>" : "<p class='empty'>" + esc(word("deal.empty")) + "</p>";
    }
    return "<div class='block commit' id='deal-commit'><div><h4>" + esc(word("deal.seller")) + "</h4>" + side("seller") +
      "</div><div><h4>" + esc(word("deal.buyer")) + "</h4>" + side("buyer") + "</div></div>";
  }
  function payloadHtml(v) {
    var payload = Object.assign({}, v.rec.payload || {}, {StageName: v.stage});
    return "<details class='more block'><summary>" + esc(word("deal.payload")) + "</summary><p class='muted'>" +
      esc(word("deal.payloadnote")) + "</p><pre class='payload'>" + esc(JSON.stringify(payload, null, 2)) + "</pre></details>";
  }

  /* The staircase: the stage each deal call reached, on a time axis with the close date and the audit week. */
  function auditDate() {
    var found = null;
    DEAL.forEach(function (id) {
      var a = rawAi(CALLS[id]);
      (a ? a.facts : []).forEach(function (f) {
        if (found || f.field !== "critical_event") { return; }
        var m = new RegExp("(" + MONTHS.join("|") + ") (\\d{1,2})").exec(f.value);
        if (m) {
          var y = ymd(CALLS[id].date).y;
          found = y + "-" + String(MONTHS.indexOf(m[1]) + 1).padStart(2, "0") + "-" + String(parseInt(m[2], 10)).padStart(2, "0");
        }
      });
    });
    return found;
  }
  function stairSvg(sel) {
    var body = $("#record-body"), wide = body && body.clientWidth >= 400;
    /* On a phone the chart is drawn at the width it shows and its labels keep their size instead of shrinking with the
       chart. Below 320px the date labels go a half size down so the close date and the audit week keep apart. */
    var cs = body && !wide && phone() && win.getComputedStyle ? win.getComputedStyle(body) : null;
    var fit = cs ? body.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) : 0;
    fit = fit >= 260 ? Math.min(360, Math.round(fit)) : 0;
    var W = wide ? 420 : fit || 360, H = 222, L = wide ? 128 : 92, R = fit ? 6 : 10, T = 30, B = 38;
    var names = CC.crm.stages.map(function (s) { return s.name; }), n = names.length;
    var lv = DEAL.map(function (id) { return names.indexOf(stageAfter(id)); });
    var lastId = DEAL[DEAL.length - 1], lastRec = recordOf(lastId), wholeRec = recordOf(lastId, true);
    var closeIso = lastRec && lastRec.fields.close_date && lastRec.fields.close_date.value;
    var closeAll = wholeRec && wholeRec.fields.close_date && wholeRec.fields.close_date.value;
    var audit = auditDate(), d0 = dayNum(CALLS[DEAL[0]].date) - 3;
    var d1 = Math.max(dayNum(CALLS[lastId].date) + 10, closeAll ? dayNum(closeAll) + 7 : 0, audit ? dayNum(audit) + 4 : 0);
    function x(d) { return L + (d - d0) * (W - L - R) / (d1 - d0); }
    function y(i) { return T + (n - 1 - i) * (H - T - B) / (n - 1); }
    var base = H - B, cur = DEAL.indexOf(sel), parts = [];
    if (audit) {
      parts.push("<rect class='audit-band' x='" + f1(x(dayNum(audit))) + "' y='" + (T - 8) + "' width='" + f1(x(dayNum(audit) + 4) -
        x(dayNum(audit))) + "' height='" + (base - T + 8) + "'/>");
    }
    names.forEach(function (name, i) {
      var cls = cur >= 0 && i === lv[cur] ? "stage-lbl on" : "stage-lbl";
      parts.push("<line class='grid' x1='" + L + "' x2='" + (W - R) + "' y1='" + f1(y(i)) + "' y2='" + f1(y(i)) + "'/>");
      if (!wide && name.length > 14 && name.indexOf(" ") > 0) {
        var cut = name.indexOf(" ");
        parts.push("<text class='" + cls + "' x='" + (L - 10) + "' y='" + f1(y(i) - 2) + "' text-anchor='end'>" + esc(name.slice(0, cut)) +
          "<tspan x='" + (L - 10) + "' dy='12'>" + esc(name.slice(cut + 1)) + "</tspan></text>");
      } else {
        parts.push("<text class='" + cls + "' x='" + (L - 10) + "' y='" + f1(y(i) + 4) + "' text-anchor='end'>" + esc(name) + "</text>");
      }
    });
    if (closeIso) {
      parts.push("<line class='deadline' x1='" + f1(x(dayNum(closeIso))) + "' x2='" + f1(x(dayNum(closeIso))) + "' y1='" + (T - 8) +
        "' y2='" + base + "'/>");
    }
    parts.push("<line class='axis' x1='" + L + "' x2='" + (W - R) + "' y1='" + base + "' y2='" + base + "'/>");
    var pts = [], prev = 0;
    DEAL.forEach(function (id, i) {
      var cx = x(dayNum(CALLS[id].date));
      pts.push([cx, y(prev)], [cx, y(lv[i])]);
      prev = lv[i];
    });
    parts.push("<path class='step' data-path='main' d='M" + pts.map(function (p) { return f1(p[0]) + " " + f1(p[1]); }).join(" L") + "'/>");
    var lx = pts[pts.length - 1][0], ly = pts[pts.length - 1][1];
    if (closeIso && x(dayNum(closeIso)) > lx) {
      parts.push("<path class='step ahead' d='M" + f1(lx) + " " + f1(ly) + " L" + f1(x(dayNum(closeIso))) + " " + f1(ly) + "'/>");
    }
    var lastA = ai(CALLS[lastId]), waiting = lastA && (lastA.concessions || []).length && !S.approved && prev + 1 < n;
    if (waiting) {
      parts.push("<path class='step wait' d='M" + f1(lx) + " " + f1(ly - 9) + " L" + f1(lx) + " " + f1(y(prev + 1) + 6) + "'/>");
      parts.push("<circle class='ghost' cx='" + f1(lx) + "' cy='" + f1(y(prev + 1)) + "' r='6'/>");
      parts.push("<text class='note' x='" + f1(lx + 12) + "' y='" + f1(y(prev + 1) + 4) + "'>" + esc(word("stair.wait")) + "</text>");
    }
    DEAL.forEach(function (id, i) {
      var cx = x(dayNum(CALLS[id].date)), cy = y(lv[i]), on = i === cur, prevDate = i ? CALLS[DEAL[i - 1]].date : null;
      if (on) { parts.push("<circle class='halo' cx='" + f1(cx) + "' cy='" + f1(cy) + "' r='14'/>"); }
      parts.push("<g class='node" + (on ? " on" : "") + "' data-node='" + esc(id) + "'><circle cx='" + f1(cx) + "' cy='" + f1(cy) +
        "' r='9'/><text x='" + f1(cx) + "' y='" + f1(cy + 3.5) + "' text-anchor='middle'>" + (i + 1) + "</text></g>");
      var label = wide || !prevDate || ymd(prevDate).m !== ymd(CALLS[id].date).m ? monthDay(CALLS[id].date) :
        String(ymd(CALLS[id].date).d);
      parts.push("<text class='date-lbl" + (on ? " on" : "") + "' x='" + f1(cx) + "' y='" + (base + 16) + "' text-anchor='middle'>" +
        esc(label) + "</text>");
    });
    if (closeIso) {
      parts.push("<text class='date-lbl' x='" + f1(x(dayNum(closeIso))) + "' y='" + (base + 16) + "' text-anchor='middle'>" +
        esc(word("stair.close", {date: monthDay(closeIso)})) + "</text>");
    }
    if (audit) {
      parts.push("<text class='date-lbl' x='" + f1(x(dayNum(audit) + 4)) + "' y='" + (base + 16) + "' text-anchor='end'>" +
        esc(word("stair.audit")) + "</text>");
    }
    return "<svg class='stair-svg" + (fit && fit < 320 ? " snug" : "") + "' viewBox='0 0 " + W + " " + H + "' role='img' aria-label='" +
      esc(word("stair.title")) + "'>" +
      parts.join("") + "</svg>";
  }
  CCP.stairLevels = function () {
    var names = CC.crm.stages.map(function (s) { return s.name; });
    return DEAL.map(function (id) { return names.indexOf(stageAfter(id)); });
  };

  /* ------------------------------------------------------------------ the email panel */
  function tableFor(c, a, approved) {
    var key = "_t" + (approved ? "a" : "");
    if (!a[key]) {
      var facts = a.facts.map(function (f) {
        return {id: f.id, field: f.field, value: f.value, number: f.number === undefined ? null : f.number,
          unit: f.unit === undefined ? null : f.unit, kind: f.kind, date: f.date === undefined ? null : f.date,
          quotes: (f.ev || []).map(function (e) { return e[1]; })};
      });
      var t = checker.table(facts, c.date, c.roster, c.companies, c.segs.map(function (g) { return g.text; }).join("\n"));
      a[key] = approved ? checker.approve(t, a.concessions) : t;
    }
    return a[key];
  }
  CCP.tableFor = function (callId, approved) { var c = CALLS[callId]; return tableFor(c, ai(c), approved); };
  function draftOf(a) { return S.approved && a.emailApproved ? a.emailApproved : a.email; }
  function draftText(d) { return d.sentences.map(function (x) { return x.text; }).join(" "); }
  /* The draft with each claim underlined. marks are ranges to wrap whole, the sentences approval added, and since a
     claim never crosses a sentence the wrappers only ever open and close between claims. */
  function claimsHtml(c, text, claims, marks) {
    var out = "", pos = 0, cuts = [];
    (marks || []).forEach(function (m) {
      cuts.push({at: m[0], o: 1, tag: "<span class='new-sent' title='" + esc(word("email.newsent")) + "'>"});
      cuts.push({at: m[1], o: 0, tag: "</span>"});
    });
    cuts.sort(function (x, y) { return x.at - y.at || x.o - y.o; });
    function plain(from, to) {
      var s = "";
      while (cuts.length && cuts[0].at <= to) {
        var k = cuts.shift(), at = Math.max(from, k.at);
        s += esc(text.slice(from, at)) + k.tag;
        from = at;
      }
      return s + esc(text.slice(from, to));
    }
    claims.slice().sort(function (x, y) { return x.start - y.start; }).forEach(function (cl, i) {
      if (cl.start < pos) { return; }
      var f = cl.fact ? factIn(c.id, cl.fact) : null;
      out += plain(pos, cl.start) + "<span class='claim " + esc(cl.status) + "' tabindex='0' data-claim='" + i + "'" +
        evAttr(c.id, f) + ">" + esc(text.slice(cl.start, cl.end)) + "</span>";
      pos = cl.end;
    });
    return out + plain(pos, text.length);
  }
  function checkText(c, a, text) {
    var t = tableFor(c, a, S.approved), parts = checker.checkEmail(text, t), claims = [], pos = 0;
    parts.forEach(function (p) {
      var at = text.indexOf(p.sentence, pos);
      if (at < 0) { at = pos; }
      p.claims.forEach(function (cl) { claims.push(Object.assign({}, cl, {start: cl.start + at, end: cl.end + at})); });
      pos = at + p.sentence.length;
    });
    return claims;
  }
  CCP.checkText = function (callId, text) { var c = CALLS[callId]; return checkText(c, ai(c), text); };
  function reasonHtml(c, cl) {
    var r = cl.reason || "";
    if (cl.fact) {
      var f = factIn(c.id, cl.fact);
      r = r.replace(" (" + cl.fact + ")", "").replace("matches " + cl.fact, "matches what the call said").replace(", " + cl.fact, "");
      return esc(cap(r)) + (f ? ". <span class='muted'>" + esc(f.value) + "</span>" + factChips(c.id, f) : "");
    }
    return esc(cap(r));
  }
  function findingsHtml(c, claims) {
    var bad = claims.filter(function (x) { return x.status !== "supported"; });
    var kinds = U["email.kind"] || {}, st = U["email.status"] || {};
    var summary = "<p class='summary-line' id='email-summary'>" + esc(word("email.summary", {n: claims.length,
      ok: claims.length - bad.length, bad: bad.length})) + "</p>";
    var list = bad.concat(claims.filter(function (x) { return x.status === "supported"; })).map(function (x) {
      return "<li class='" + esc(x.status) + "'><span class='st " + esc(x.status) + "'>" + esc(st[x.status] || x.status) +
        "</span><span class='what'>" + esc(kinds[x.kind] || x.kind) + " · " + esc(x.text) + "</span><br>" + reasonHtml(c, x) + "</li>";
    }).join("");
    return summary + (bad.length ? "" : "<p class='muted'>" + esc(word("email.clean")) + "</p>") +
      "<ul class='findings' id='findings'>" + list + "</ul>";
  }
  function emailClaims(a, text) {
    var d = draftOf(a), claims = [], pos = 0;
    d.sentences.forEach(function (x) {
      var at = text.indexOf(x.text, pos);
      x.claims.forEach(function (cl) { claims.push(Object.assign({}, cl, {start: cl.start + at, end: cl.end + at})); });
      pos = at + x.text.length;
    });
    return claims;
  }
  /* The sentences approval added: the approved draft's sentences that use an approved concession, as ranges of the
     draft's text. The model writes the approved draft again from the start, so its other sentences can be worded
     differently without approval having added anything to them. */
  function addedOnApproval(a, text) {
    if (!S.approved || !a.emailApproved || S.text !== null) { return []; }
    var gave = {}, out = [], pos = 0;
    (a.concessions || []).forEach(function (id) { gave[id] = true; });
    a.emailApproved.sentences.forEach(function (x) {
      var at = text.indexOf(x.text, pos);
      if (at < 0) { return; }
      if ((x.facts || []).some(function (id) { return gave[id]; })) { out.push([at, at + x.text.length]); }
      pos = at + x.text.length;
    });
    return out;
  }
  function waitHtml(id, key) {
    return "<div class='block replay-wait' id='" + id + "'><p>" + esc(word(key)) + "</p></div>";
  }
  function emailHtml(c, a) {
    if (live(c)) { return waitHtml("email-card", "replay.email"); }
    if (!a || !a.email) { return "<p class='empty'>" + esc(word("email.nodraft")) + "</p>"; }
    var d = draftOf(a), text = S.text === null ? draftText(d) : S.text;
    var claims = S.text === null ? emailClaims(a, text) : checkText(c, a, text);
    var added = addedOnApproval(a, text);
    CCP.lastClaims = claims;
    var to = c.people.filter(function (p) { return p.side === "buyer"; }).map(function (p) { return p.name; });
    var samples = Object.keys(c.samples || {}).map(function (k) {
      return "<button type='button' class='btn small' data-sample='" + esc(k) + "'>" + esc((U["email.sample"] || {})[k] || k) + "</button>";
    }).join("");
    var body = S.editing ? "<textarea class='editor' id='editor' spellcheck='false'>" + esc(text) + "</textarea>" +
      "<div class='email-draft checked' id='checked'>" + claimsHtml(c, text, claims) + "</div>" :
      "<div class='email-draft' id='draft'>" + claimsHtml(c, text, claims, added) + "</div>";
    var approvedNote = S.approved && a.emailApproved && S.text === null ? "<p class='muted'>" + esc(word("email.approvedraft")) +
      "</p>" + (added.length ? "" : "<p class='muted' id='email-leftout'>" + esc(word("email.leftout")) + "</p>") : "";
    var approve = a.concessions && a.concessions.length ? "<label class='follow'><input type='checkbox' id='approve-email'" +
      (S.approved ? " checked" : "") + ">" + esc(word("deal.approve")) + "</label>" : "";
    return "<div class='block' id='email-card'><div class='mail-head'><div><span>" + esc(word("email.to")) + "</span>" +
      esc(joinNames(to)) + "</div><div><span>" + esc(word("email.subject")) + "</span>" + esc(d.subject) + "</div></div>" +
      "<p class='byline'>" + esc(word("email.by", {model: modelLabel()})) + "</p>" + approvedNote + body +
      "<div class='email-actions'>" + approve + "<span class='grow'></span><button type='button' class='btn small' id='edit'>" +
      esc(S.editing ? word("email.done") : word("email.edit")) + "</button>" + (S.text !== null ? "<button type='button' " +
      "class='btn small' id='reset'>" + esc(word("email.reset")) + "</button>" : "") + "</div><div class='samples' id='samples'>" +
      "<span class='muted'>" + esc(word("email.samples")) + "</span>" + samples + "</div></div><div class='block' " +
      "id='email-findings'><h3>" + esc(word("email.findings")) + "</h3>" + findingsHtml(c, claims) + "</div><p class='limits'>" +
      esc(word("email.limits")) + "</p>";
  }
  function recheck() {
    var c = call(), a = ai(c), ed = $("#editor");
    if (!ed) { return; }
    S.text = ed.value;
    var claims = checkText(c, a, S.text);
    CCP.lastClaims = claims;
    $("#checked").innerHTML = claimsHtml(c, S.text, claims);
    $("#email-findings").innerHTML = "<h3>" + esc(word("email.findings")) + "</h3>" + findingsHtml(c, claims);
    soonThreads(false);
  }
  /* A sample goes in before the sign-off. Added after a sign-off with no full stop ("Best, Marcus Webb") it would run
     into the name and read as one sentence. */
  function addSample(kind) {
    var c = call(), a = ai(c), s = (c.samples || {})[kind];
    if (!s) { return; }
    var d = draftOf(a), base = (S.text === null ? draftText(d) : S.text).replace(/\s*$/, "");
    var last = d.sentences.length ? d.sentences[d.sentences.length - 1] : null;
    var sign = last && !(last.facts || []).length ? last.text : "";
    var at = sign && base.slice(-sign.length) === sign ? base.length - sign.length : -1;
    S.text = at > 0 ? base.slice(0, at) + s + " " + base.slice(at) : base + (/[.!?]$/.test(base) ? " " : ". ") + s;
    S.editing = true;
    renderPanel(false, true);
  }

  /* ------------------------------------------------------------------ the coach panel */
  function scoreOf(parts, w) {
    var total = 0, sum = 0;
    Object.keys(parts).forEach(function (k) { var x = Number(w[k] || 0); total += x; sum += parts[k] * x; });
    return total ? Math.round(sum / total * 100) : 0;
  }
  CCP.scoreOf = scoreOf;
  function metricText(k, m) {
    var v = m[k];
    if (v === undefined || v === null) { return ""; }
    if (k === "talk_share" || k === "open_share") { return pct(v); }
    if (/_s$/.test(k)) { return (Math.round(v * 10) / 10) + " s"; }
    return String(Math.round(v * 10) / 10);
  }
  function longestTurn(c) {
    var best = null;
    c.segs.forEach(function (g) { if (g.sp === c.rep && (!best || g.e - g.s > best.e - best.s)) { best = g; } });
    return best;
  }
  /* Each measure against its good range from the rubric. The bar is the measure itself, never its score. */
  function measuresHtml(c) {
    var m = c.coach.metrics, comps = (CC.rubric || {}).components || {}, labels = U["coach.metrics"] || {}, defs = U["coach.defs"] || {};
    var mm = Object.assign({}, m, {talk_share: m.seller_share}), turn = longestTurn(c);
    return Object.keys(comps).map(function (k) {
      var comp = comps[k], v = mm[k];
      if (v === undefined || v === null) { return ""; }
      var lo = Math.min(comp.bad[0], comp.good[0]), hi = Math.max(comp.bad[1], comp.good[1]);
      if (hi <= lo) { hi = lo + 1; }
      function at(x) { return Math.max(0, Math.min(100, (x - lo) / (hi - lo) * 100)); }
      var g0 = at(comp.good[0]), g1 = at(comp.good[1]);
      var ev = k === "longest_monologue_s" && turn ? " data-ev='" + esc(turn.id) + "'" : "";
      return "<div class='measure' title='" + esc(defs[k] || "") + "'" + ev + "><span class='m-label'>" + esc(labels[k] || comp.label) +
        "</span><b class='m-val'>" + esc(metricText(k, mm)) + "</b><span class='band'><i class='good' data-left='" + g0.toFixed(1) +
        "' data-width='" + Math.max(1.5, g1 - g0).toFixed(1) + "'></i><i class='mark' data-left='" + at(v).toFixed(1) +
        "'></i></span></div>";
    }).join("");
  }
  function coachHtml(c, a) {
    if (live(c)) { return waitHtml("coach-score", "replay.coach"); }
    var m = c.coach.metrics, rep = person(c, c.rep), labels = U["coach.metrics"] || {}, tags = U["coach.qtag"] || {};
    var talk = "<div class='talk'><h4>" + esc(word("coach.talk")) + "</h4>" + c.people.map(function (p) {
      var share = (m.talk_share || {})[p.code] || 0;
      return "<div class='talk-row'><span>" + esc(p.name) + "</span><span class='bar-track'><span class='bar-fill " + esc(p.side) +
        "' data-width='" + (share * 100).toFixed(1) + "'></span></span><span class='mono'>" + pct(share) + "</span></div>";
    }).join("") + "</div>";
    var steps = a ? "<div class='measure plain'><span class='m-label'>" + esc(labels.next_step_quality) + "</span><b class='m-val'>" +
      a.steps[0] + " of " + a.steps[1] + "</b></div>" : "";
    var sliders = Object.keys(c.coach.parts).map(function (k) {
      return "<label><span>" + esc((CC.rubric.components[k] || {}).label || k) + "</span><input type='range' min='0' max='40' " +
        "data-weight='" + esc(k) + "' value='" + esc(weights[k]) + "'><span class='mono' data-wv='" + esc(k) + "'>" + esc(weights[k]) +
        "</span></label>";
    }).join("");
    var asked = c.coach.asked || [];
    var qs = asked.map(function (q) {
      return "<li data-ev='" + esc(q.segment) + "'><span>" + esc(q.text) + "</span><span class='qtag " + (q.open ? "open" : "closed") +
        "'>" + esc(tags[q.open ? "open" : "closed"] || "") + "</span></li>";
    }).join("");
    var note;
    if (a && a.coach) {
      var list = function (items) {
        return "<ul class='note-list'>" + items.map(function (x) {
          return "<li data-ev='" + esc(x.segment) + "'>" + esc(x.text) + " " + chip(c.id, x.segment) + "</li>";
        }).join("") + "</ul>";
      };
      note = "<div class='block' id='coach-note'><h3>" + esc(word("coach.note")) + "</h3><p class='byline'>" +
        esc(word("coach.noteby", {model: modelLabel()})) + "</p><h4>" + esc(word("coach.strengths")) + "</h4>" +
        list(a.coach.strengths) + "<h4>" + esc(word("coach.improve")) + "</h4>" + list(a.coach.improvements) + "</div>";
    } else {
      note = "<div class='block' id='coach-note'><h3>" + esc(word("coach.note")) + "</h3><p class='empty'>" + esc(word("coach.nonote")) +
        "</p></div>";
    }
    var multiples = "<div class='block' id='coach-deal'><h3>" + esc(word("coach.deal")) + "</h3><p class='muted'>" +
      esc(word("coach.dealnote")) + "</p><div class='multiples'>" + ["talk_share", "longest_monologue_s", "questions_per_10min",
        "open_share", "patience_s", "rep_interruptions"].map(function (k) {
        var vals = DEAL.map(function (id) { var x = CALLS[id].coach.metrics; return k === "talk_share" ? x.seller_share : x[k]; });
        var top = Math.max.apply(null, vals.map(function (v) { return v || 0; })) || 1;
        return "<div><h4>" + esc(labels[k] || k) + "</h4>" + vals.map(function (v, i) {
          var mmx = {};
          mmx[k] = v;
          return "<div class='mrow" + (DEAL[i] === c.id ? " on" : "") + "'><span class='bar-track'><span class='bar-fill seller' " +
            "data-width='" + ((v || 0) / top * 100).toFixed(1) + "'></span></span><span class='mono'>" + esc("Call " + (i + 1) + " " +
            metricText(k, mmx)) + "</span></div>";
        }).join("") + "</div>";
      }).join("") + "</div></div>";
    return "<div class='block' id='coach-score'><div class='score-hero'><b id='score'>" + scoreOf(c.coach.parts, weights) +
      "</b><span class='muted'>" + esc(word("coach.outof")) + "</span></div><p class='byline'>" +
      esc(word("coach.rep", {name: rep.name, role: rep.role})) + "</p><div class='measures'>" + measuresHtml(c) + steps +
      "</div><p class='note'>" + esc(word("coach.band")) + "</p>" + talk + "</div><details class='more block weights' " +
      "id='coach-weights' open><summary>" + esc(word("coach.weights")) + "</summary><p class='muted'>" + esc(word("coach.weightsnote")) +
      "</p>" + sliders + "</details><div class='block' id='coach-qs'><div class='block-head'><h3>" +
      esc(word("coach.qs", {name: rep.name.split(" ")[0]})) + "</h3><span>" + esc(word("coach.qcount", {n: asked.length})) +
      "</span></div><ul class='qs'>" + qs + "</ul></div>" + note + multiples;
  }

  /* ------------------------------------------------------------------ the threads */
  /* Which item ties to which line, without any geometry. The node check reads this. */
  function threadPlan() {
    var c = call();
    return $$("#record-body [data-ev]").map(function (el) {
      var i = c.segIndex[el.getAttribute("data-ev")];
      return {seg: el.getAttribute("data-ev"), row: i === undefined ? null : "seg-" + i,
        found: i !== undefined && !!doc.getElementById("seg-" + i)};
    });
  }
  CCP.threadPlan = threadPlan;
  /* Queues one redraw for the next frame. animate is true to draw every thread in, "new" for only the items that just
     landed, and false to redraw in place. */
  function soonThreads(animate) {
    if (animate) { T.animate = animate === "new" && T.animate !== true ? "new" : true; }
    if (T.queued) { return; }
    T.queued = true;
    raf(function () {
      T.queued = false;
      var an = T.animate;
      T.animate = false;
      drawThreads(an);
      drawTour();
    });
  }
  function link(w, mid) {
    var left = $("#calls"), pick = $("#calls .on"), title = $("#call-title");
    if (!left || !pick || !title) { return ""; }
    var lr = left.getBoundingClientRect(), cr = pick.getBoundingClientRect(), tr = title.getBoundingClientRect();
    var ax = lr.right - w.left, bx = mid.left - w.left;
    if (!(bx - ax > 8)) { return ""; }
    var y = cr.top + cr.height * 0.5, off = "";
    if (y < lr.top + 12) { y = lr.top + 12; off = " off"; }
    if (y > lr.bottom - 12) { y = lr.bottom - 12; off = " off"; }
    var ay = y - w.top, by = tr.top + tr.height * 0.5 - w.top, g = (bx - ax) * 0.62;
    return "<path class='thread link" + off + "' data-k='L' d='M" + f1(ax) + " " + f1(ay) + " C" + f1(ax + g) + " " + f1(ay) + " " +
      f1(bx - g) + " " + f1(by) + " " + f1(bx) + " " + f1(by) + "'/><circle class='tdot link" + off + "' data-k='L' cx='" + f1(ax) +
      "' cy='" + f1(ay) + "' r='3.5'/><circle class='tdot link' data-k='L' data-end='b' cx='" + f1(bx) + "' cy='" + f1(by) +
      "' r='3.5'/>";
  }
  /* Draws a curve from each item in view to its line in the transcript. A line out of view gets a dashed end at the
     transcript's edge, and those ends fan out in order. */
  function drawThreads(animate) {
    var svg = $("#threads"), work = $("#work"), pane = $("#transcript"), body = $("#record-body"), midEl = $("#call");
    if (!svg) { return; }
    if (!work || !pane || !body || !midEl || S.view !== "work" || !work.getBoundingClientRect) { svg.innerHTML = ""; return; }
    var w = work.getBoundingClientRect(), mid = midEl.getBoundingClientRect(), pr = pane.getBoundingClientRect();
    var br = body.getBoundingClientRect(), head = $(".pane-head", pane), hd = head ? head.getBoundingClientRect() : pr;
    var x1 = mid.right - w.left, x2 = br.left - w.left;
    $$("[data-k]", body).forEach(function (el) { el.removeAttribute("data-k"); });
    if (!(x2 - x1 > 8)) { svg.innerHTML = ""; return; }
    var top = hd.bottom + 8, bottom = pr.bottom - 10, g = (x2 - x1) * 0.62, c = call(), items = [];
    $$("[data-ev]", body).forEach(function (el) {
      var r = el.getBoundingClientRect();
      if (r.top < br.top + 2 || r.top > br.bottom - 14 || (!r.width && !r.height)) { return; }
      var i = c.segIndex[el.getAttribute("data-ev")], row = i === undefined ? null : doc.getElementById("seg-" + i);
      if (!row) { return; }
      var rr = row.getBoundingClientRect(), y = rr.top + 15;
      items.push({el: el, i: i, y1: y, y2: r.top + 11, off: y < top ? -1 : y > bottom ? 1 : 0,
        side: row.classList.contains("buyer") ? "buyer" : "seller", fresh: el.classList.contains("landing")});
    });
    items.filter(function (it) { return it.off < 0; }).sort(function (p, q) { return q.y1 - p.y1; })
      .forEach(function (it, k) { it.y1 = top + Math.min(k, 6) * 7; });
    items.filter(function (it) { return it.off > 0; }).sort(function (p, q) { return p.y1 - q.y1; })
      .forEach(function (it, k) { it.y1 = bottom - Math.min(k, 6) * 7; });
    var out = "";
    items.forEach(function (it, k) {
      var a = it.y1 - w.top, b = it.y2 - w.top, off = it.off ? " off" : "";
      it.el.setAttribute("data-k", String(k));
      out += "<path class='thread " + it.side + off + "' data-k='" + k + "' data-seg='" + esc(c.segs[it.i].id) + "' d='M" + f1(x1) + " " +
        f1(a) + " C" + f1(x1 + g) + " " + f1(a) + " " + f1(x2 - g) + " " + f1(b) + " " + f1(x2) + " " + f1(b) + "'/>" +
        "<circle class='tdot " + it.side + off + "' data-k='" + k + "' cx='" + f1(x1) + "' cy='" + f1(a) + "' r='3.5'/>" +
        "<circle class='tdot " + it.side + "' data-k='" + k + "' data-end='b' cx='" + f1(x2) + "' cy='" + f1(b) + "' r='3.5'/>";
    });
    out += link(w, mid);
    svg.setAttribute("viewBox", "0 0 " + f1(w.width) + " " + f1(w.height));
    svg.setAttribute("width", f1(w.width));
    svg.setAttribute("height", f1(w.height));
    svg.innerHTML = out;
    grow(svg, items, animate);
    growLink(svg, animate);
    if (T.hot) { lightThread(T.hot); }
    else if (T.row) { lightRow(T.row); }
  }
  /* Draws threads in from the transcript side: every one with a stagger, or only the items that just landed. A thread
     still drawing when the overlay or the panel is rebuilt (a scroll, a replay tick) is found again by what its item
     holds and picks up where it was, so nothing gets cut. */
  function grow(svg, items, mode) {
    var now = Date.now(), was = T.anim || [], next = [];
    T.anim = next;
    if (calm() || !win.requestAnimationFrame) { return; }
    items.forEach(function (it, k) {
      var p = $("path.thread[data-k='" + k + "']", svg), a = null, key = keyOf(it.el);
      if (!p) { return; }
      if (mode === true || (mode === "new" && it.fresh)) {
        a = {key: key, start: now, delay: mode === true ? k * 40 : 0, dur: mode === true ? 560 : 760};
      } else {
        for (var j = 0; j < was.length; j++) { if (was[j].key === key) { a = was[j]; break; } }
        if (!a || now >= a.start + a.delay + a.dur) { return; }
      }
      next.push(a);
      var into = Math.max(0, now - a.start - a.delay), wait = Math.max(0, a.start + a.delay - now);
      if (p.classList.contains("off") || !p.getTotalLength) {
        p.style.opacity = "0";
        win.setTimeout(function () { p.style.opacity = ""; }, wait + 300);
      } else {
        var len = p.getTotalLength(), left = Math.max(1, a.dur - into);
        p.style.strokeDasharray = len + " " + len;
        p.style.strokeDashoffset = String(len * (1 - Math.min(1, into / a.dur)));
        raf(function () {
          raf(function () {
            p.style.transition = "stroke-dashoffset " + Math.round(left) + "ms cubic-bezier(.25, .7, .25, 1) " + wait + "ms, opacity .2s";
            p.style.strokeDashoffset = "0";
          });
        });
      }
      $$("circle.tdot[data-k='" + k + "']", svg).forEach(function (d) {
        var show = (d.getAttribute("data-end") === "b" ? a.dur - 80 : 0) - into + wait;
        if (show <= 0) { return; }
        d.style.opacity = "0";
        win.setTimeout(function () { d.style.opacity = ""; }, show);
      });
    });
  }
  /* The left line draws in once, then slides from the old card to the new one when the call changes. */
  function growLink(svg, mode) {
    var p = $("path.link", svg), d = p ? p.getAttribute("d") : "";
    var dot = $$("circle.tdot.link", svg).filter(function (x) { return x.getAttribute("data-end") !== "b"; })[0];
    if (p && !calm() && win.requestAnimationFrame) {
      if (T.slide && T.linkD && T.linkD !== d) {
        morph(p, T.linkD);
        if (dot && T.linkY !== null) { moveFrom(dot, 0, T.linkY - num(dot, "cy")); }
      } else if (mode === true && !T.linkD && p.getTotalLength && !p.classList.contains("off")) {
        var len = p.getTotalLength();
        p.style.strokeDasharray = len + " " + len;
        p.style.strokeDashoffset = String(len);
        raf(function () {
          raf(function () {
            p.style.transition = "stroke-dashoffset 560ms cubic-bezier(.25, .7, .25, 1)";
            p.style.strokeDashoffset = "0";
          });
        });
      }
    }
    if (p) { T.slide = false; }
    T.linkD = d;
    T.linkY = dot ? num(dot, "cy") : null;
  }
  function lightThread(el) {
    T.hot = el;
    T.row = null;
    var svg = $("#threads"), key = el ? el.getAttribute("data-k") : null;
    if (svg) {
      svg.classList.toggle("focus", key !== null);
      $$("path.thread", svg).forEach(function (p) { p.classList.toggle("hot", key !== null && p.getAttribute("data-k") === key); });
    }
    $$("#rows .lit").forEach(function (x) { x.classList.remove("lit"); });
    $$("#record-body .lit-item").forEach(function (x) { x.classList.remove("lit-item"); });
    if (el) {
      var i = call().segIndex[el.getAttribute("data-ev")], row = i === undefined ? null : doc.getElementById("seg-" + i);
      if (row) { row.classList.add("lit"); }
    }
  }
  function lightRow(row) {
    T.row = row;
    T.hot = null;
    var svg = $("#threads"), id = row.getAttribute("data-seg"), any = false;
    if (svg) {
      $$("path.thread", svg).forEach(function (p) {
        var on = p.getAttribute("data-seg") === id;
        p.classList.toggle("hot", on);
        any = any || on;
      });
      svg.classList.toggle("focus", any);
    }
    $$("#record-body .lit-item").forEach(function (x) { x.classList.remove("lit-item"); });
    $$("#record-body [data-ev]").forEach(function (x) { if (x.getAttribute("data-ev") === id) { x.classList.add("lit-item"); } });
  }
  /* Sends the transcript to a line and marks it. The thread follows the line as it scrolls. */
  function goRow(segId) {
    var c = call(), i = c.segIndex[segId], row = i === undefined ? null : doc.getElementById("seg-" + i);
    if (!row) { return; }
    $$("#rows .lit").forEach(function (x) { x.classList.remove("lit"); });
    row.classList.add("lit");
    S.userScroll = Date.now();
    scrollRow(row, 0.35, true);
  }
  /* On a fresh call or a panel switch the transcript goes to where the open panel's evidence starts, so the threads
     land on lines in view. It leaves the transcript alone once the call is playing, has been played, or has been
     scrolled by hand, and when the first quoted line is already in the top part of the pane. */
  function settle() {
    var pane = $("#transcript"), c = call();
    if (!pane || S.playing || S.t > 0 || S.userScroll || !pane.clientHeight) { return; }
    var first = null;
    $$("#record-body [data-ev]").forEach(function (el) {
      var i = c.segIndex[el.getAttribute("data-ev")];
      if (i !== undefined && (first === null || i < first)) { first = i; }
    });
    var row = first === null ? null : doc.getElementById("seg-" + first);
    if (!row || typeof row.offsetTop !== "number") { return; }
    var under = headUnder(), top = pane.scrollTop + under;
    if (row.offsetTop < top || row.offsetTop > top + (pane.clientHeight - under) * 0.6) { scrollRow(row, 0.25, false); }
  }

  /* ------------------------------------------------------------------ motion */
  function num(el, name) { return parseFloat(el.getAttribute(name)) || 0; }
  /* Starts an element where it was and lets CSS carry it to where it is now. */
  function moveFrom(el, dx, dy) {
    if (!el || !el.style || calm() || !win.requestAnimationFrame || (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5)) { return; }
    el.style.transition = "none";
    el.style.transform = "translate(" + f1(dx) + "px, " + f1(dy) + "px)";
    if (el.getBoundingClientRect) { el.getBoundingClientRect(); }
    raf(function () {
      raf(function () {
        el.style.transition = "transform 560ms cubic-bezier(.3, .7, .2, 1)";
        el.style.transform = "";
      });
    });
  }
  /* The same for a path's shape. A browser without the CSS d property shows the new shape at once. */
  function morph(el, from) {
    var to = el && el.getAttribute("d");
    if (!el || !el.style || !from || from === to || calm() || !win.requestAnimationFrame) { return; }
    el.style.transition = "none";
    el.style.d = "path('" + from + "')";
    if (el.getBoundingClientRect) { el.getBoundingClientRect(); }
    raf(function () {
      raf(function () {
        el.style.transition = "d 560ms cubic-bezier(.3, .7, .2, 1)";
        el.style.d = "path('" + to + "')";
      });
    });
  }
  /* Where the staircase's open call sat before a redraw, so the redraw can move it instead of jumping. A new call slides
     the halo across, and a new stage for the same call lifts the node and reshapes the line. */
  function stairState() {
    var svg = $("#stair svg");
    if (!svg) { return null; }
    var node = $(".node.on circle", svg), halo = $(".halo", svg), main = $("[data-path='main']", svg);
    return {call: S.call, node: node ? [num(node, "cx"), num(node, "cy")] : null,
      halo: halo ? [num(halo, "cx"), num(halo, "cy")] : null, d: main ? main.getAttribute("d") : ""};
  }
  function stairMotion(was) {
    var svg = $("#stair svg");
    if (!was || !svg) { return; }
    var g = $(".node.on", svg), node = g ? $("circle", g) : null, halo = $(".halo", svg), main = $("[data-path='main']", svg);
    if (halo && was.halo) { moveFrom(halo, was.halo[0] - num(halo, "cx"), was.halo[1] - num(halo, "cy")); }
    if (g && node && was.node && was.call === S.call) { moveFrom(g, was.node[0] - num(node, "cx"), was.node[1] - num(node, "cy")); }
    if (main) { morph(main, was.d); }
  }
  /* Items that just appeared in the record, found by what they hold, so they can land with a short highlight. */
  var LANDS = "[data-fact], [data-ev], .new-sent, .rec dd";
  function keyOf(el) {
    return (el.tagName || "") + "|" + (el.getAttribute("data-fact") || "") + "|" + (el.getAttribute("data-ev") || "") + "|" +
      String(el.textContent || "").slice(0, 80);
  }
  function keysIn(root) {
    var out = {};
    $$(LANDS, root).forEach(function (el) { out[keyOf(el)] = true; });
    return out;
  }
  function markLanding(root, seen) {
    var first = null;
    $$(LANDS, root).forEach(function (el) {
      if (seen[keyOf(el)]) { return; }
      var cell = String(el.tagName).toLowerCase() === "dd";
      el.classList.add(cell ? "bump" : "landing");
      if (!first && !cell) { first = el; }
    });
    return first;
  }
  /* During a replay the record scrolls to the item that just landed, unless the reader has scrolled it lately. */
  function bringIn(el) {
    var body = $("#record-body");
    if (!el || !body || !body.clientHeight || !el.getBoundingClientRect || Date.now() - S.bodyScroll < 4000) { return; }
    var r = el.getBoundingClientRect(), b = body.getBoundingClientRect();
    if (r.top >= b.top + 8 && r.bottom <= b.bottom - 8) { return; }
    var to = Math.max(0, body.scrollTop + r.top - b.top - b.height * 0.35);
    if (body.scrollTo) { body.scrollTo({top: to, behavior: calm() ? "auto" : "smooth"}); } else { body.scrollTop = to; }
  }
  /* When a replay ends, the email and the scorecard fill in. Bars and marks grow from zero and the score counts up. */
  function fillIn(root) {
    T.fill = false;
    if (calm() || !win.requestAnimationFrame || !root.classList) { return; }
    root.classList.add("filling");
    $$("[data-width]", root).forEach(function (el) { el.style.width = "0%"; });
    $$(".band [data-left]", root).forEach(function (el) { el.style.left = "0%"; });
    $$(".findings li", root).forEach(function (el, i) { el.style.animationDelay = (i * 60) + "ms"; });
    if (root.getBoundingClientRect) { root.getBoundingClientRect(); }
    raf(function () { raf(function () { place(root); }); });
    var score = $("#score", root), end = score ? parseInt(score.textContent, 10) || 0 : 0, t0 = Date.now();
    function count() {
      var k = Math.min(1, (Date.now() - t0) / 900);
      if (score) { score.textContent = String(Math.round(end * (1 - Math.pow(1 - k, 3)))); }
      if (k < 1) { raf(count); }
    }
    if (score) { count(); }
    win.setTimeout(function () { root.classList.remove("filling"); }, 1600);
  }
  function replayNote() {
    return "<p class='replay-note' id='replay-note'><i></i><span>" + esc(word("replay.note")) + "</span></p>";
  }
  function replayButton() {
    var b = $("#replay");
    if (!b) { return; }
    b.textContent = word(S.replay ? "replay.all" : "replay.start");
    b.classList.toggle("on", !!S.replay);
    b.setAttribute("aria-pressed", S.replay ? "true" : "false");
  }
  /* Replay runs the open call from the start, and the record builds itself as each quote is said. */
  function startReplay() {
    if (S.present) { present(0); }
    if (S.view !== "work") { showHow(false); }
    pause();
    S.replay = true; S.heard = -1; S.userScroll = 0; S.bodyScroll = 0; S.editing = false; S.text = null;
    S.stageNow = stageAfter(S.call);
    T.hot = null; T.row = null;
    replayButton();
    var pane = $("#transcript");
    if (pane && typeof pane.scrollTop === "number") { pane.scrollTop = 0; }
    seek(0, false);
    play();
  }
  function endReplay(fill) {
    if (!S.replay) { return; }
    S.replay = false; S.heard = -1;
    replayButton();
    T.fill = !!fill;
    renderCalls();
    renderPanel(true, true);
    confirmCount();
  }
  /* Each tick of the clock during a replay: redraw the record when another fact has been said, or end at the end. */
  function replayTick() {
    var c = call(), a = c ? rawAi(c) : null;
    if (!S.replay || !a) { return; }
    if (!S.playing && S.t >= length() - 0.25) { endReplay(true); return; }
    var n = heardCount(c, a);
    if (n === S.heard) { return; }
    var grew = S.heard >= 0 && n > S.heard;
    S.heard = n;
    renderPanel(false, true, grew);
    var st = stageAfter(c.id);
    if (st !== S.stageNow) { S.stageNow = st; renderCalls(); }
    confirmCount();
  }
  CCP.replay = startReplay;
  CCP.endReplay = endReplay;

  /* ------------------------------------------------------------------ the views */
  function crumbs() {
    var c = call(), i = DEAL.indexOf(c.id), d = $("#crumb-deal"), h = $("#crumb-call");
    if (d) { d.textContent = joinNames(c.companies || []); }
    if (h) { h.textContent = (i >= 0 ? cap(callName(c.id)) + " · " : "") + c.title; }
  }
  function renderAll(animate) {
    renderCalls();
    renderCall();
    renderPanel(animate, false);
    crumbs();
  }
  function setCall(id) {
    if (!CALLS[id] || id === S.call) { return; }
    pause();
    S.call = id; S.t = 0; S.editing = false; S.text = null; S.nowSeg = -1; S.userScroll = 0; T.hot = null; T.row = null;
    S.replay = false; S.heard = -1; T.slide = true;
    var pane = $("#transcript");
    renderAll(true);
    pane = $("#transcript");
    if (pane && typeof pane.scrollTop === "number") { pane.scrollTop = 0; }
    settle();
  }
  function setPanel(name) {
    if (PANELS.indexOf(name) < 0) { return; }
    S.panel = name;
    T.hot = null;
    T.row = null;
    renderPanel(true, false);
    settle();
  }
  function setModel(id) { S.model = id; S.text = null; S.editing = false; S.replay = false; S.heard = -1; renderAll(true); }
  function showHow(on) {
    S.view = on ? "how" : "work";
    var work = $("#work"), how = $("#how"), body = doc.body || $("body");
    if (work) { work.hidden = on; }
    if (how) { how.hidden = !on; }
    if (body && body.classList) { body.classList.toggle("mode-how", on); body.classList.toggle("mode-work", !on); }
    if (on) {
      pause();
      loadCode();
      if (win.scrollTo) { win.scrollTo(0, 0); }
    } else { soonThreads(true); }
    writeHash();
  }
  CCP.view = function () { return S.view; };

  /* ------------------------------------------------------------------ the code view */
  function loadCode() {
    if (win.CCCODE) { codeTree(); return; }
    if (S.codeLoading) { return; }
    S.codeLoading = true;
    var s = doc.createElement("script");
    s.src = "code.js";
    s.onload = codeTree;
    if (doc.body && doc.body.appendChild) { doc.body.appendChild(s); }
  }
  function codeTree() {
    var tree = $("#code-tree"), code = win.CCCODE;
    if (!tree || !code) { return; }
    var folder = null, out = "";
    Object.keys(code.files).sort().forEach(function (rel) {
      var top = rel.indexOf("/") >= 0 ? rel.split("/")[0] + "/" : "";
      if (top !== folder) { folder = top; if (top) { out += "<p>" + esc(top) + "</p>"; } }
      out += "<button type='button' data-file='" + esc(rel) + "'>" + esc(rel.slice(top.length)) + "</button>";
    });
    tree.innerHTML = out;
    openFile(S.codeFile || code.default);
  }
  function openFile(rel) {
    var code = win.CCCODE;
    if (!code || !code.files[rel]) { S.codeFile = rel; return; }
    S.codeFile = rel;
    $("#code-path").textContent = rel;
    $("#code-body").textContent = code.files[rel];
    $$("#code-tree button, .cfeat").forEach(function (b) { b.classList.toggle("on", b.getAttribute("data-file") === rel); });
  }

  /* ------------------------------------------------------------------ presenter mode */
  function firstFact(c, field) {
    var a = ai(c);
    return a ? a.facts.filter(function (f) { return f.field === field && f.ev && f.ev.length; })[0] : null;
  }
  /* Centers an element by scrolling the pane that holds it, and on a phone moves to its screen first. It never scrolls
     the page itself, which on a phone would carry the fixed presenter out of view. How it works scrolls the window. */
  function reveal(el) {
    if (!el || !el.getBoundingClientRect) { return; }
    var card = el.closest && el.closest("#calls, #call, #record");
    if (card && phone()) { toScreen(card.id, false); }
    var style = win.getComputedStyle;
    for (var p = el.parentElement; p && p !== doc.body; p = p.parentElement) {
      if (style && p.scrollHeight > p.clientHeight + 4 && /auto|scroll/.test(style(p).overflowY)) {
        var r = el.getBoundingClientRect(), q = p.getBoundingClientRect();
        p.scrollTop += r.top - q.top - Math.max(0, (q.height - r.height) / 2);
        return;
      }
    }
    if (S.view === "how" && win.scrollTo) {
      var b = el.getBoundingClientRect();
      win.scrollTo(0, (win.scrollY || 0) + b.top - Math.max(0, ((win.innerHeight || 0) - b.height) / 2));
    }
  }
  function spot(sel) {
    $$(".spot").forEach(function (e) { e.classList.remove("spot"); });
    var el = typeof sel === "string" ? $(sel) : sel;
    if (el) { el.classList.add("spot"); reveal(el); }
    return el;
  }
  function go(callId, panel) {
    if (S.view !== "work") { showHow(false); }
    if (callId !== S.call) { setCall(callId); }
    if (panel !== S.panel) { setPanel(panel); } else { renderPanel(false, false); }
  }
  STEPS = [
    function () { go("deal-1", "fields"); var f = firstFact(call(), "pain"); if (f) { seekSeg(f.ev[0][0], true); spot("#seg-" + call().segIndex[f.ev[0][0]]); } },
    function () { go("deal-1", "fields"); var f = firstFact(call(), "metrics"); if (f) { spot(".field[data-field='metrics']"); seekSeg(f.ev[0][0], true); } },
    function () { go("deal-3", "deal"); spot("#deal-changes"); },
    function () { go("deal-3", "deal"); spot("#deal-stage"); },
    function () { go("deal-3", "deal"); spot("#approve-box") || spot("#deal-commit"); },
    function () { S.text = null; S.editing = false; go("deal-3", "email"); spot("#email-card"); },
    function () { go("deal-3", "email"); S.text = null; addSample("promise"); spot("#email-findings"); },
    function () { go("deal-1", "coach"); spot("#coach-score"); },
    function () { go("deal-1", "coach"); spot("#coach-weights"); },
    function () { showHow(true); spot("#how-score"); },
    function () { showHow(true); spot("#how-compare"); },
    function () { showHow(true); openFile("engine/claims.py"); spot("#how-code"); }
  ];
  function present(n) {
    var box = $("#presenter");
    if (S.replay) { S.replay = false; S.heard = -1; replayButton(); }
    if (!n) {
      S.present = 0;
      box.hidden = true;
      $$(".spot").forEach(function (e) { e.classList.remove("spot"); });
      writeHash();
      soonThreads(false);
      return;
    }
    S.present = n;
    pause();
    STEPS[n - 1]();
    if (S.view === "work" && doc.body) {
      doc.body.scrollTop = 0;
      if (doc.scrollingElement) { doc.scrollingElement.scrollTop = 0; }
    }
    var titles = U["present.steps"] || {}, texts = U["present.text"] || {};
    box.innerHTML = "<h3>" + esc(titles[n]) + "</h3><p>" + esc(texts[n]) + "</p><div class='row'><span>" +
      esc(word("present.step", {n: n, total: STEPS.length})) + "</span><button type='button' class='btn' data-present='back'" +
      (n === 1 ? " disabled" : "") + ">" + esc(word("present.back")) + "</button><button type='button' class='btn primary' " +
      "data-present='next'>" + esc(n === STEPS.length ? word("present.exit") : word("present.next")) + "</button><button " +
      "type='button' class='btn' data-present='exit'>" + esc(word("present.exit")) + "</button></div>";
    box.hidden = false;
    writeHash();
    soonThreads(false);
  }
  CCP.present = present;

  /* ------------------------------------------------------------------ the tour */
  /* The presenter's spotlight. The window dims except the card in focus and the transcript lines it points to, and
     the threads between them draw on top of the dim. A fixed set of cutouts moves from step to step, so the light
     glides instead of jumping. */
  var HOLES = 10;
  function tourPlan() {
    var focus = S.present ? $(".spot") : null, c = call(), out = [];
    if (!focus || S.view !== "work") { return out; }
    var seg = focus.getAttribute("data-seg");
    if (seg && focus.closest && focus.closest("#rows")) {
      $$("#record-body [data-ev='" + seg + "']").forEach(function (el) { out.push({item: el, row: focus}); });
      return out.slice(0, HOLES - 1);
    }
    var own = focus.closest && focus.closest("#record-body [data-ev]");
    (own ? [own] : $$("[data-ev]", focus)).forEach(function (el) {
      var i = c.segIndex[el.getAttribute("data-ev")], row = i === undefined ? null : doc.getElementById("seg-" + i);
      if (row) { out.push({item: el, row: row}); }
    });
    return out.slice(0, HOLES - 1);
  }
  CCP.tourPlan = function () {
    return tourPlan().map(function (l) { return {seg: l.item.getAttribute("data-ev"), row: l.row.id}; });
  };
  function cut(el, pad) {
    var r = el.getBoundingClientRect();
    return {x: r.left - pad, y: r.top - pad, w: r.width + pad * 2, h: r.height + pad * 2};
  }
  function setHole(rect, b) {
    ["x", "y", "width", "height"].forEach(function (k, i) {
      var v = f1([b.x, b.y, b.w, b.h][i]);
      rect.setAttribute(k, v);
      if (rect.style) { rect.style[k] = v + "px"; }
    });
  }
  function drawTour() {
    var svg = $("#tour"), root = doc.body, focus = S.present ? $(".spot") : null;
    if (!svg) { return; }
    if (!focus || !focus.getBoundingClientRect) {
      if (T.tour) { svg.setAttribute("hidden", ""); if (root) { root.classList.remove("touring"); } }
      T.tour = 0;
      return;
    }
    var fresh = T.tour !== S.present, W = f1(win.innerWidth || 0), H = f1(win.innerHeight || 0);
    T.tour = S.present;
    if (!$("#tour-cut", svg)) {
      var holes = "";
      for (var h = 0; h < HOLES; h++) { holes += "<rect class='hole' rx='12' fill='#000' x='0' y='0' width='0' height='0'/>"; }
      svg.innerHTML = "<defs><mask id='tour-cut' maskUnits='userSpaceOnUse'><rect class='all' fill='#fff' x='0' y='0'/>" + holes +
        "</mask></defs><rect class='shade all' x='0' y='0' mask='url(#tour-cut)'/><g id='tour-threads'></g>";
    }
    svg.removeAttribute("hidden");
    if (root) { root.classList.add("touring"); }
    $$(".all", svg).forEach(function (r) { r.setAttribute("width", W); r.setAttribute("height", H); });
    var boxes = [cut(focus, 8)], lines = "", seen = {};
    var pane = $("#transcript"), mid = $("#call"), body = $("#record-body");
    if (pane && mid && body && S.view === "work") {
      var pr = pane.getBoundingClientRect(), head = $(".pane-head", pane), top = head ? head.getBoundingClientRect().bottom : pr.top;
      var x1 = mid.getBoundingClientRect().right, x2 = body.getBoundingClientRect().left, g = (x2 - x1) * 0.62;
      tourPlan().forEach(function (l, k) {
        var y1 = l.row.getBoundingClientRect().top + 15, y2 = l.item.getBoundingClientRect().top + 11;
        if (y1 < top || y1 > pr.bottom - 10 || x2 - x1 < 8) { return; }
        if (!seen[l.row.id] && l.row !== focus) { seen[l.row.id] = 1; boxes.push(cut(l.row, 3)); }
        if (l.item !== focus && !focus.contains(l.item)) { boxes.push(cut(l.item, 3)); }
        var side = l.row.classList.contains("buyer") ? "buyer" : "seller";
        lines += "<path class='thread " + side + "' pathLength='1' d='M" + f1(x1) + " " + f1(y1) + " C" + f1(x1 + g) + " " + f1(y1) +
          " " + f1(x2 - g) + " " + f1(y2) + " " + f1(x2) + " " + f1(y2) + "'/><circle class='tdot " + side + "' cx='" + f1(x1) +
          "' cy='" + f1(y1) + "' r='3.5'/><circle class='tdot " + side + "' cx='" + f1(x2) + "' cy='" + f1(y2) + "' r='3.5'/>";
      });
    }
    var center = {x: boxes[0].x + boxes[0].w / 2, y: boxes[0].y + boxes[0].h / 2, w: 0, h: 0};
    svg.classList.toggle("glide", fresh && !calm());
    $$(".hole", svg).forEach(function (rect, i) { setHole(rect, boxes[i] || center); });
    var group = $("#tour-threads", svg);
    if (group) {
      group.innerHTML = lines;
      group.classList.toggle("fresh", fresh && !calm());
    }
    if (fresh) { win.setTimeout(function () { svg.classList.remove("glide"); }, 700); }
  }

  /* ------------------------------------------------------------------ the phone screens */
  /* Below 901 pixels the three cards sit side by side as screens to swipe between, and the time chips stand in for
     the threads. Picking a call, a chip or an item goes to the call. */
  var SCREENS = ["calls", "call", "record"];
  function phone() { return !!(win.matchMedia && win.matchMedia("(max-width: 900px)").matches); }
  function markScreen(name) {
    S.screen = name;
    $$("[data-screen]").forEach(function (b) {
      var on = b.getAttribute("data-screen") === name;
      b.classList.toggle("on", on);
      b.setAttribute("aria-current", on ? "true" : "false");
    });
  }
  function toScreen(name, smooth) {
    if (SCREENS.indexOf(name) < 0) { return; }
    markScreen(name);
    var work = $("#work");
    if (!phone() || !work || !work.clientWidth) { return; }
    var left = SCREENS.indexOf(name) * work.clientWidth;
    if (work.scrollTo) { work.scrollTo({left: left, behavior: smooth && !calm() ? "smooth" : "auto"}); }
    else { work.scrollLeft = left; }
  }
  function screenSeen() {
    var work = $("#work");
    if (!phone() || !work || !work.clientWidth) { return; }
    var name = SCREENS[Math.max(0, Math.min(2, Math.round(work.scrollLeft / work.clientWidth)))];
    if (name !== S.screen) { markScreen(name); }
  }
  CCP.screen = function () { return S.screen; };
  CCP.steps = STEPS.length;
  CCP.state = function () {
    return {t: S.t, playing: S.playing, call: S.call, panel: S.panel, view: S.view, model: S.model,
      audio: P.audio ? P.audio.currentTime : null,
      blob: !!P.url, replay: S.replay, heard: S.heard, rate: S.rate, audible: audible()};
  };

  /* ------------------------------------------------------------------ the popover */
  function pop(el, html) {
    var box = $("#pop");
    if (!box) { return; }
    if (!el) { box.hidden = true; return; }
    box.innerHTML = html;
    box.hidden = false;
    if (el.getBoundingClientRect) {
      var r = el.getBoundingClientRect();
      box.style.left = Math.max(8, Math.min((win.innerWidth || 1200) - 340, r.left + (win.scrollX || 0))) + "px";
      box.style.top = (r.bottom + (win.scrollY || 0) + 6) + "px";
    }
  }

  /* ------------------------------------------------------------------ events */
  function stop(e) { if (e && e.preventDefault) { e.preventDefault(); } }
  doc.addEventListener("click", function (e) {
    var t = e.target, el;
    if (!t || !t.closest) { return; }
    if ((el = t.closest("[data-panel-tab]"))) { if (S.present) { present(0); } setPanel(el.getAttribute("data-panel-tab")); return; }
    if ((el = t.closest("[data-screen]"))) { toScreen(el.getAttribute("data-screen"), true); return; }
    if ((el = t.closest("[data-pick]"))) {
      if (S.present) { present(0); }
      setCall(el.getAttribute("data-pick"));
      if (phone()) { toScreen("call", true); }
      return;
    }
    if ((el = t.closest("#how-link"))) { stop(e); showHow(true); return; }
    if ((el = t.closest("#how-back")) || (el = t.closest("#home"))) { stop(e); showHow(false); return; }
    if ((el = t.closest("#play"))) { if (S.playing) { pause(); } else { play(); } return; }
    if ((el = t.closest("#replay"))) { if (S.replay) { endReplay(true); } else { startReplay(); } return; }
    if ((el = t.closest(".chip[data-seg]"))) {
      var cid = el.getAttribute("data-call"), sid = el.getAttribute("data-seg");
      if (S.view !== "work") { showHow(false); }
      if (cid !== S.call) { setCall(cid); }
      seekSeg(sid, true);
      goRow(sid);
      pop(null);
      if (phone()) { toScreen("call", true); }
      return;
    }
    if ((el = t.closest(".claim[data-claim]"))) {
      var cl = (CCP.lastClaims || [])[parseInt(el.getAttribute("data-claim"), 10)];
      if (cl) {
        var st = U["email.status"] || {};
        pop(el, "<p><span class='st " + esc(cl.status) + "'>" + esc(st[cl.status] || cl.status) + "</span></p><p>" + reasonHtml(call(), cl) + "</p>");
      }
      if (el.getAttribute("data-ev")) { goRow(el.getAttribute("data-ev")); }
      return;
    }
    if ((el = t.closest(".seg[data-i]"))) { seek(call().segs[parseInt(el.getAttribute("data-i"), 10)].s, true); return; }
    if ((el = t.closest("#record-body [data-ev]")) && !t.closest("button, input, label, a, select, textarea, summary")) {
      goRow(el.getAttribute("data-ev"));
      if (phone()) { toScreen("call", true); }
      return;
    }
    if ((el = t.closest("[data-sample]"))) { addSample(el.getAttribute("data-sample")); return; }
    if ((el = t.closest("#edit"))) {
      if (!S.editing && S.text === null) { S.text = draftText(draftOf(ai())); }
      S.editing = !S.editing;
      renderPanel(false, true);
      return;
    }
    if ((el = t.closest("#reset"))) { S.text = null; S.editing = false; renderPanel(false, true); return; }
    if ((el = t.closest("#present"))) { present(1); return; }
    if ((el = t.closest("[data-present]"))) {
      var act = el.getAttribute("data-present");
      if (act === "exit" || (act === "next" && S.present === STEPS.length)) { present(0); }
      else { present(S.present + (act === "next" ? 1 : -1)); }
      return;
    }
    if ((el = t.closest("[data-file]"))) {
      openFile(el.getAttribute("data-file"));
      /* On a phone the file opens below the list and the page brings it into view. */
      var pane = phone() ? $(".code-pane") : null;
      if (pane && pane.scrollIntoView) { pane.scrollIntoView({block: "nearest", behavior: calm() ? "auto" : "smooth"}); }
      return;
    }
    if (!t.closest("#pop")) { pop(null); }
  });
  doc.addEventListener("change", function (e) {
    var t = e.target;
    if (!t) { return; }
    if (t.id === "pick-model") { setModel(t.value); return; }
    if (t.id === "follow") { S.follow = !!t.checked; return; }
    if (t.id === "speed") { setRate(parseFloat(t.value)); return; }
    if (t.id === "approve" || t.id === "approve-email") {
      S.approved = !!t.checked;
      S.text = null;
      renderCalls();
      renderPanel(false, true, true);
      return;
    }
    if (t.getAttribute && t.getAttribute("data-rule")) {
      S.off[t.getAttribute("data-rule")] = !t.checked;
      renderCalls();
      renderPanel(false, true);
    }
  });
  doc.addEventListener("input", function (e) {
    var t = e.target;
    if (!t) { return; }
    if (t.id === "search") { S.search = t.value; markSearch(); return; }
    if (t.id === "cutoff") {
      S.cutoff = parseInt(t.value, 10) / 100;
      var lab = $("label[for='cutoff']");
      if (lab) { lab.textContent = word("transcript.cutoff", {p: Math.round(S.cutoff * 100)}); }
      markSearch();
      confirmCount();
      if (S.panel === "fields") { renderPanel(false, true); }
      return;
    }
    if (t.id === "scrub") { seek(parseInt(t.value, 10) / 10, false); return; }
    if (t.id === "editor") {
      win.clearTimeout(S.typing);
      S.typing = win.setTimeout(recheck, 120);
      return;
    }
    if (t.getAttribute && t.getAttribute("data-weight")) {
      var k = t.getAttribute("data-weight");
      weights[k] = parseInt(t.value, 10);
      var v = $("[data-wv='" + k + "']");
      if (v) { v.textContent = String(weights[k]); }
      $("#score").textContent = String(scoreOf(call().coach.parts, weights));
    }
  });
  doc.addEventListener("keydown", function (e) {
    var t = e.target || {}, tag = (t.tagName || "").toLowerCase();
    if (t.closest && t.closest("[role='tab']") && (e.key === "ArrowRight" || e.key === "ArrowLeft")) {
      var tabs = $$("[data-panel-tab]"), i = tabs.indexOf(t.closest("[role='tab']"));
      var next = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
      setPanel(next.getAttribute("data-panel-tab"));
      if (next.focus) { next.focus(); }
      e.preventDefault();
      return;
    }
    if (tag === "input" || tag === "textarea" || tag === "select" || (t.isContentEditable)) { return; }
    if (e.key === "Escape") { pop(null); if (S.present) { present(0); } return; }
    if (S.view !== "work") { return; }
    if (e.key === " " && tag !== "button") { e.preventDefault(); if (S.playing) { pause(); } else { play(); } }
    else if (e.key === "ArrowRight") { e.preventDefault(); seek(now() + 5, false); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); seek(now() - 5, false); }
  });
  doc.addEventListener("mouseover", function (e) {
    var t = e.target;
    if (!t || !t.closest || S.view !== "work") { return; }
    var item = t.closest("#record-body [data-ev]");
    if (item) { if (item !== T.hot) { lightThread(item); } return; }
    var row = t.closest("#rows .seg");
    if (row) { if (row !== T.row) { lightRow(row); } return; }
    if (T.hot || T.row) { lightThread(null); }
  });
  ["wheel", "touchmove"].forEach(function (type) {
    doc.addEventListener(type, function (e) {
      if (e.target && e.target.closest && e.target.closest("#transcript")) { S.userScroll = Date.now(); }
      if (e.target && e.target.closest && e.target.closest("#record-body")) { S.bodyScroll = Date.now(); }
    }, {passive: true});
  });
  doc.addEventListener("scroll", function (e) {
    var t = e.target;
    if (t && t.id === "work") { screenSeen(); }
    if (t && (t.id === "transcript" || t.id === "record-body" || t.id === "calls")) { soonThreads(false); }
    else if (S.present) { soonThreads(false); }
  }, true);
  if (win.addEventListener) {
    win.addEventListener("resize", function () {
      if (phone()) { toScreen(S.screen || "call", false); }
      soonThreads(false);
    });
  }

  /* ------------------------------------------------------------------ start */
  var start = readHash(win.location && win.location.hash);
  if (start.call && CALLS[start.call]) { S.call = start.call; }
  if (start.panel) { S.panel = start.panel; }
  var mp = $("#pick-model");
  if (mp) { mp.value = S.model; }
  /* On a touch screen the model list shows a face of its own at the header's size. The real list sits invisible on
     top of the face at 16px, so a phone doesn't zoom the page when it's tapped, and takes the tap (app.css). */
  if (mp && TOUCH && mp.parentNode) {
    var face = doc.createElement("span");
    face.className = "pick-face";
    face.setAttribute("aria-hidden", "true");
    mp.parentNode.classList.add("faced");
    mp.parentNode.appendChild(face);
    var showModel = function () { var o = mp.options[mp.selectedIndex]; face.textContent = o ? o.text : ""; };
    mp.addEventListener("change", showModel);
    showModel();
  }
  renderAll(false);
  if (start.how) { showHow(true); }
  if (start.present) { present(start.present); }
  function begin() {
    if (T.started) { return; }
    T.started = true;
    markScreen(S.screen || "call");
    if (phone()) { toScreen(S.screen || "call", false); }
    settle();
    drawThreads(true);
  }
  if (doc.fonts && doc.fonts.ready && doc.fonts.ready.then) { doc.fonts.ready.then(begin); win.setTimeout(begin, 900); }
  else { begin(); }
})();
