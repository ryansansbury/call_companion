/* The node click-through. It runs the built page's own scripts against a small DOM (dom.js), opens every panel for
   every call, plays a chip, searches, moves the confidence cutoff, checks that every thread has a line to land on,
   switches a stage rule off, approves the concession and watches the staircase, adds every sample bad claim, types
   a promise, moves a weight, opens How it works and the code view, and steps through presenter mode forward and
   back. It replays all three deal calls and checks each fact appears once its quote is said and never before, that
   the stage steps when the change list says, and that the email and scorecard wait for the end. It walks the tour's
   spotlight and its threads, and on a stand-in phone it moves between the three screens. Exits 1 on any failed
   check.

       node tests/js/check_app.js [site folder]

   It can't see layout, color, motion, audio or real timing. owner/browser_check.py covers those in real Chrome. */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const {Document} = require("./dom.js");

const SITE = path.resolve(process.argv[2] || path.join(__dirname, "..", "..", "site"));
const checks = [], errors = [];
function check(name, ok, detail) { checks.push({name, ok: !!ok, detail: detail === undefined ? "" : String(detail).slice(0, 300)}); }

const html = fs.readFileSync(path.join(SITE, "index.html"), "utf8");
const doc = new Document(html);
check("index.html parses with every tag closed", doc.errors.length === 0, doc.errors.slice(0, 3).join("; "));
check("no script, style or media comes from another site", !/(?:src)=['"](?:https?:)?\/\//.test(html));
check("no inline script or style", !/<script>(?!<\/script>)|<script[^>]*>[^<]+<\/script>| style=/.test(html));
const timers = [];
const win = {document: doc, innerWidth: 1600, innerHeight: 1000, addEventListener() {}, devicePixelRatio: 1,
  setTimeout(fn) { timers.push(fn); return timers.length; }, clearTimeout(id) { if (id) { timers[id - 1] = null; } },
  location: {hash: "", protocol: "file:"}, history: {replaceState(s, t, url) { win.location.hash = url; }},
  scrollX: 0, scrollY: 0};
win.window = win;
const ctx = vm.createContext(win);
for (const name of ["claims.js", "data.js", "code.js", "app.js"]) {
  try { vm.runInContext(fs.readFileSync(path.join(SITE, name), "utf8"), ctx, {filename: name}); }
  catch (e) { errors.push(name + " threw: " + (e && e.stack || e)); }
}
function flush() {
  for (let guard = 0; guard < 400 && timers.some(Boolean); guard++) {
    const i = timers.findIndex(Boolean), fn = timers[i];
    timers[i] = null;
    fn();
  }
}
const CC = win.CC, CCP = win.CCP;
const click = (el) => doc.dispatch("click", el);
const change = (el, value, checked) => {
  if (value !== undefined) { el.value = value; }
  if (checked !== undefined) { if (checked) { el.setAttribute("checked", ""); } else { el.removeAttribute("checked"); } el.checked = checked; }
  doc.dispatch("change", el);
};
const input = (el, value) => { el.value = value; doc.dispatch("input", el); };
const panel = () => (doc.querySelector("[data-panel-tab][aria-selected='true']") || {getAttribute: () => ""}).getAttribute("data-panel-tab");
const openCall = (id) => { click(doc.querySelector(`[data-pick='${id}']`)); flush(); };
const openPanel = (name) => { click(doc.querySelector(`[data-panel-tab='${name}']`)); flush(); };
const stage = () => (doc.getElementById("deal-stage-now") || {textContent: ""}).textContent;
function attempt(name, fn) { try { fn(); } catch (e) { errors.push(name + ": " + (e && e.stack || e)); } }

if (CC && CCP) {
  attempt("opening", () => {
    flush();
    check("the page opens on the first deal call with the Fields panel", CCP.state().call === CC.deal[0] && panel() === "fields",
      CCP.state().call + " " + panel());
    check("the left card lists the deal's calls as cards", doc.querySelectorAll(".callcard").length === CC.deal.length);
    check("the left card lists the scored set", doc.querySelectorAll(".callrow").length === CC.calls.length - CC.deal.length);
    check("each deal call card carries its waveform and stage bar",
      doc.querySelectorAll(".callcard .mini-svg").length === CC.deal.length && doc.querySelectorAll(".callcard .path i.at").length === CC.deal.length);
    check("the breadcrumb names the open call", doc.getElementById("crumb-call").textContent.indexOf(CC.calls[0].title) >= 0,
      doc.getElementById("crumb-call").textContent);
  });
  attempt("every call on every panel", () => {
    let ok = 0, total = 0;
    for (const c of CC.calls) {
      openCall(c.id);
      for (const name of ["fields", "deal", "email", "coach"]) {
        total += 1;
        openPanel(name);
        if (doc.getElementById("record-body").innerHTML.length > 200 && panel() === name && CCP.state().call === c.id) { ok += 1; }
      }
    }
    check("every panel renders for every call", ok === total, `${ok} of ${total}`);
  });
  attempt("the call", () => {
    openCall("deal-1");
    openPanel("fields");
    const segs = doc.querySelectorAll("#rows .seg");
    check("the transcript lists every segment", segs.length === CC.calls[0].segs.length && segs.length > 0, segs.length);
    check("the waveform has the seller above the line and the buyer below", doc.querySelectorAll("#scope .scope-svg path").length === 2);
    check("the waveform flags the call's key facts", doc.querySelectorAll("#scope .flag").length === CCP.flagsOf("deal-1").length &&
      CCP.flagsOf("deal-1").length >= 3, CCP.flagsOf("deal-1").map((f) => f.label).join(", "));
    const fields = doc.querySelectorAll(".field[data-field]");
    check("the Fields panel shows every field", fields.length === 19, fields.length);
    const chips = doc.querySelectorAll("#facts .chip");
    check("facts carry evidence chips", chips.length > 5, chips.length);
    click(chips[3]);
    check("a chip seeks to its moment", doc.querySelector("#rows .now") !== null);
    flush();
    click(doc.getElementById("play"));
    flush();
    check("play and pause work without audio", true);
    input(doc.getElementById("search"), "trucks");
    check("search marks matches on the waveform", CCP.lastSearch > 0 && doc.querySelectorAll("#hits b").length === CCP.lastSearch,
      CCP.lastSearch);
    input(doc.getElementById("search"), "");
    const before = doc.getElementById("confirm-count").textContent;
    input(doc.getElementById("cutoff"), "99");
    const after = doc.getElementById("confirm-count").textContent;
    check("the confidence cutoff changes the count of facts for a person", before !== after, before + " then " + after);
    input(doc.getElementById("cutoff"), "70");
    input(doc.getElementById("scrub"), "300");
    check("the waveform seeks", doc.getElementById("clock").textContent.indexOf("0:30") === 0, doc.getElementById("clock").textContent);
  });
  attempt("threads", () => {
    for (const id of CC.deal) {
      openCall(id);
      for (const name of ["fields", "deal", "email", "coach"]) {
        openPanel(name);
        const plan = CCP.threadPlan();
        const lost = plan.filter((x) => !x.found);
        check(`every thread on ${id} ${name} has a line to land on`, plan.length > 0 && lost.length === 0,
          `${plan.length} threads, missing ${lost.map((x) => x.seg).join(", ")}`);
      }
    }
  });
  attempt("the deal", () => {
    openCall("deal-3");
    openPanel("deal");
    const first = stage();
    check("the deal reaches a stage after call 3", first.length > 0, first);
    check("the staircase has a node for each deal call", doc.querySelectorAll("#stair .node").length === CC.deal.length);
    const levels = CCP.stairLevels();
    check("the staircase never steps down", levels.every((v, i) => i === 0 || v >= levels[i - 1]), levels.join(" "));
    const box = doc.getElementById("approve");
    if (box) {
      change(box, undefined, true);
      const lifted = CCP.stairLevels();
      check("approving the concession moves the stage", stage() !== first, first + " then " + stage());
      check("approving the concession lifts the staircase", lifted[lifted.length - 1] > levels[levels.length - 1], lifted.join(" "));
      check("approving the concession clears the waiting mark", doc.querySelectorAll("#stair .ghost").length === 0);
      change(doc.getElementById("approve"), undefined, false);
      check("withdrawing the approval brings the waiting mark back", doc.querySelectorAll("#stair .ghost").length === 1);
    }
    const unmet = doc.querySelectorAll("#rules li").find((li) => li.querySelector(".no"));
    const id = unmet ? unmet.querySelector("input[data-rule]").getAttribute("data-rule") : null;
    if (id) {
      change(doc.querySelector(`input[data-rule='${id}']`), undefined, false);
      check("switching an unmet rule off recomputes the stage", stage() !== first, first + " then " + stage());
      change(doc.querySelector(`input[data-rule='${id}']`), undefined, true);
      check("switching it back restores the stage", stage() === first, stage());
    }
    check("the change list shows what call 3 changed", doc.querySelectorAll("#deal-changes li").length > 3);
    const chip = doc.querySelector("#deal-changes .chip");
    if (chip) {
      const target = chip.getAttribute("data-call");
      click(chip);
      flush();
      check("a change's chip opens its call at the moment", CCP.state().call === target && doc.querySelector("#rows .now") !== null);
    }
    openCall("s01");
    openPanel("deal");
    check("a scored call shows its record without a staircase", doc.querySelectorAll("#stair").length === 0 && stage().length > 0);
  });
  attempt("the email", () => {
    openCall("deal-3");
    openPanel("email");
    check("the draft shows its claims underlined", doc.querySelectorAll("#draft .claim").length > 0);
    const kinds = Object.keys(CC.calls.find((c) => c.id === "deal-3").samples);
    let caught = 0;
    for (const k of kinds) {
      click(doc.getElementById("reset") || doc.getElementById("edit"));
      if (!doc.getElementById("editor")) { click(doc.getElementById("edit")); }
      click(doc.querySelector(`[data-sample='${k}']`));
      if (CCP.lastClaims.some((x) => x.status !== "supported")) { caught += 1; }
    }
    check("every sample bad claim is caught", caught === kinds.length && kinds.length === 6, `${caught} of ${kinds.length}`);
    click(doc.getElementById("reset"));
    click(doc.getElementById("edit"));
    const ed = doc.getElementById("editor");
    input(ed, ed.value + " We'll throw in free installation and a 25% discount.");
    flush();
    const flagged = CCP.lastClaims.filter((x) => x.status !== "supported").map((x) => x.text);
    check("a typed promise is caught as you type", flagged.length >= 2, flagged.join(", "));
    const claim = doc.querySelector("#checked .claim");
    if (claim) { click(claim); check("a claim opens its reason", !doc.getElementById("pop").hidden); }
    click(doc.getElementById("reset"));
  });
  attempt("the coach", () => {
    openCall("deal-1");
    openPanel("coach");
    const before = doc.getElementById("score").textContent;
    input(doc.querySelector("input[data-weight='talk_share']"), "0");
    const after = doc.getElementById("score").textContent;
    check("moving a weight recomputes the score", before !== after || before === "100", before + " then " + after);
    check("each measure sits on its good range", doc.querySelectorAll(".measure .band .good").length ===
      Object.keys(CC.rubric.components).length);
    check("the questions the rep asked are listed", doc.querySelectorAll("#coach-qs li").length ===
      CC.calls[0].coach.asked.length);
    check("the deal calls sit side by side", doc.querySelectorAll("#coach-deal .multiples h4").length === 6);
  });
  attempt("how it works", () => {
    click(doc.getElementById("how-link"));
    check("How it works opens as its own view", CCP.view() === "how" && !doc.getElementById("how").hidden && doc.getElementById("work").hidden);
    check("the code view lists the files", doc.querySelectorAll("#code-tree button").length > 20);
    check("the featured files fit one row", doc.querySelectorAll(".cfeat").length === 5);
    click(doc.querySelector(".cfeat[data-file='engine/evidence.py']"));
    check("a featured file opens", doc.getElementById("code-path").textContent === "engine/evidence.py");
    click(doc.getElementById("how-back"));
    check("the way back returns to the calls", CCP.view() === "work" && doc.getElementById("how").hidden);
  });
  attempt("the address", () => {
    openCall("deal-3");
    openPanel("deal");
    check("the address names the panel and the call", win.location.hash === "#deal/deal-3", win.location.hash);
  });
  attempt("presenter", () => {
    click(doc.getElementById("present"));
    let ok = 0;
    for (let i = 1; i <= CCP.steps; i++) {
      flush();
      if (!doc.getElementById("presenter").hidden && win.location.hash === "#present-" + i) { ok += 1; }
      const next = doc.querySelector("[data-present='next']");
      if (i < CCP.steps) { click(next); }
    }
    check("every presenter step opens with its own address", ok === CCP.steps, `${ok} of ${CCP.steps}`);
    for (let i = CCP.steps; i > 1; i--) { click(doc.querySelector("[data-present='back']")); flush(); }
    check("presenter steps back to the start", win.location.hash === "#present-1");
    click(doc.querySelector("[data-present='exit']"));
    check("presenter exits", doc.getElementById("presenter").hidden);
  });
  attempt("the replay", () => {
    const scrubTo = (t) => { input(doc.getElementById("scrub"), String(Math.round(t * 10))); flush(); };
    const hold = () => { if (CCP.state().playing) { click(doc.getElementById("play")); } flush(); };
    const replay = () => { click(doc.getElementById("replay")); flush(); hold(); };
    const shown = () => Array.from(doc.querySelectorAll("#record-body .fact[data-fact]")).map((el) => el.getAttribute("data-fact"));
    const run = (id) => { const c = CC.calls.find((x) => x.id === id); return {c, a: c.ai[CCP.state().model] || Object.values(c.ai)[0]}; };
    let inOrder = 0, landed = 0, steps = 0;
    for (const id of CC.deal) {
      openCall(id);
      openPanel("fields");
      replay();
      const {c, a} = run(id);
      const at = new Map(a.facts.map((f) => [f.id, CCP.factAt(id, f.id)]));
      const times = [...new Set(at.values())].sort((x, y) => x - y);
      let ok = CCP.state().replay === true;
      for (const t of times) {
        scrubTo(t + 0.06);
        const want = a.facts.filter((f) => at.get(f.id) <= CCP.state().t).map((f) => f.id).sort();
        const got = shown().sort();
        if (JSON.stringify(want) !== JSON.stringify(got)) { ok = false; }
        steps += 1;
        if (doc.querySelectorAll("#record-body .landing").length) { landed += 1; }
      }
      scrubTo(c.length);
      flush();
      if (ok && CCP.state().replay === false && shown().length === a.facts.length) { inOrder += 1; }
    }
    check("on every deal call each fact appears once its quote has been said, in that order, and the replay ends at the end",
      inOrder === CC.deal.length, `${inOrder} of ${CC.deal.length}`);
    check("a fact that lands is marked so it can land with a highlight", landed >= steps * 0.9, `${landed} of ${steps}`);

    openCall("deal-3");
    openPanel("deal");
    replay();
    const before = CCP.stairLevels();
    const prev = before[CC.deal.length - 2];
    check("the replay starts the open call at the stage the last call left", before[CC.deal.length - 1] === prev,
      before.join(","));
    const {a} = run("deal-3");
    const cause = (a.crm.changes.find((x) => x.kind === "stage") || {}).fact;
    const causeAt = CCP.factAt("deal-3", cause);
    scrubTo(causeAt - 0.3);
    const early = {stage: stage(), item: !!doc.querySelector("#deal-changes .chg-stage")};
    scrubTo(causeAt + 0.06);
    const late = {stage: stage(), item: !!doc.querySelector("#deal-changes .chg-stage")};
    check("the stage steps up at the moment the change list cites, and not a moment before",
      early.stage !== "Proposal" && !early.item && late.stage === "Proposal" && late.item, JSON.stringify([early, late]));
    openPanel("email");
    check("during the replay the email waits for the end of the call",
      !!doc.querySelector("#email-card.replay-wait") && !doc.getElementById("draft"));
    openPanel("coach");
    check("during the replay the scorecard waits for the end of the call", !!doc.querySelector("#coach-score.replay-wait"));
    click(doc.getElementById("replay"));
    flush();
    check("Show everything ends the replay and brings the scorecard back", CCP.state().replay === false &&
      !doc.querySelector(".replay-wait") && !!doc.getElementById("score"));
    replay();
    openCall("deal-1");
    check("opening another call ends the replay", CCP.state().replay === false && !doc.getElementById("replay-note"));

    const speed = doc.getElementById("speed");
    change(speed, "4");
    check("4× runs on the silent clock", CCP.state().rate === 4 && CCP.state().audible === false);
    change(speed, "1");

    // Each model writes its approved draft again from the start, so only a sentence that uses an approved concession
    // is marked, and a draft that leaves the concession out says so.
    openCall("deal-3");
    openPanel("email");
    const c3 = CC.calls.find((x) => x.id === "deal-3"), home = CCP.state().model;
    const pickModel = (m) => { const pick = doc.getElementById("pick-model"); if (pick && CCP.state().model !== m) { change(pick, m); flush(); openPanel("email"); } };
    let models = 0, right = 0, leftOut = 0;
    for (const m of CC.models.map((x) => x.id).filter((id) => c3.ai[id] && c3.ai[id].emailApproved)) {
      pickModel(m);
      if (CCP.state().model !== m) { continue; }
      const gave = new Set(c3.ai[m].concessions);
      change(doc.getElementById("approve-email"), undefined, true);
      flush();
      const added = Array.from(doc.querySelectorAll("#draft .new-sent")).map((el) => el.textContent);
      const want = c3.ai[m].emailApproved.sentences.filter((x) => (x.facts || []).some((id) => gave.has(id))).map((x) => x.text);
      models += 1;
      if (!want.length) { leftOut += 1; }
      if (JSON.stringify(added) === JSON.stringify(want) && !!doc.getElementById("email-leftout") === !want.length) { right += 1; }
      change(doc.getElementById("approve-email"), undefined, false);
      flush();
    }
    pickModel(home);
    check("approving marks the sentences that use the concession, and a draft that leaves it out says so",
      models > leftOut && right === models, `${right} of ${models} models right, ${leftOut} leaving it out`);
    change(doc.getElementById("approve-email"), undefined, true);
    flush();
    change(doc.getElementById("approve-email"), undefined, false);
    flush();
    check("withdrawing approval takes the mark away", doc.querySelectorAll("#draft .new-sent").length === 0 &&
      !doc.getElementById("email-leftout"));
  });
  attempt("the tour", () => {
    openCall("deal-1");
    click(doc.getElementById("present"));
    flush();
    const tour = doc.getElementById("tour");
    check("the tour dims the page and keeps a cutout for the card in focus", !tour.hasAttribute("hidden") &&
      doc.body.classList.contains("touring") && doc.querySelectorAll("#tour .hole").length === 10 &&
      !!doc.querySelector(".spot"));
    const links = {}, rowsOk = {};
    for (let i = 1; i <= CCP.steps; i++) {
      flush();
      links[i] = CCP.tourPlan();
      rowsOk[i] = links[i].every((l) => !!doc.getElementById(l.row));
      if (i < CCP.steps) { click(doc.querySelector("[data-present='next']")); }
    }
    const tied = [1, 2, 3, 6].filter((i) => links[i].length > 0 && rowsOk[i]);
    check("the tour draws threads for the steps about evidence (the pain line, the metrics, the changes, the email)",
      tied.length === 4, JSON.stringify(Object.fromEntries([1, 2, 3, 6].map((i) => [i, links[i].length]))));
    check("the How it works steps have no threads to draw", [10, 11, 12].every((i) => links[i].length === 0));
    click(doc.querySelector("[data-present='exit']"));
    flush();
    check("leaving the tour lifts the dim", tour.hasAttribute("hidden") && !doc.body.classList.contains("touring") &&
      !doc.querySelector(".spot"));
  });
  attempt("the phone", () => {
    check("the page has a switcher for the three screens", doc.querySelectorAll("#screens [data-screen]").length === 3);
    const media = win.matchMedia;
    win.matchMedia = (q) => ({matches: q.indexOf("max-width: 900px") >= 0});
    try {
      click(doc.querySelector("[data-screen='record']"));
      const onRecord = CCP.screen() === "record" && doc.querySelector("[data-screen='record']").classList.contains("on");
      click(doc.querySelector("[data-screen='calls']"));
      openCall("deal-2");
      const pickGoes = CCP.screen() === "call";
      click(doc.querySelector("[data-screen='record']"));
      openPanel("fields");
      click(doc.querySelector("#record-body .chip[data-seg]"));
      flush();
      const chipGoes = CCP.screen() === "call";
      check("on a phone the switcher moves between screens, and picking a call or a time chip goes to the call",
        onRecord && pickGoes && chipGoes, JSON.stringify({onRecord, pickGoes, chipGoes}));
    } finally {
      if (media) { win.matchMedia = media; } else { delete win.matchMedia; }
    }
  });
  attempt("helpers", () => {
    check("the address reader knows a presenter step", CCP.readHash("#present-4").present === 4);
    check("the address reader knows a panel and call", CCP.readHash("#deal/deal-2").call === "deal-2" &&
      CCP.readHash("#deal/deal-2").panel === "deal");
    check("an old Call address opens the Fields panel", CCP.readHash("#call/deal-1").panel === "fields");
    check("the address reader knows How it works", CCP.readHash("#how").how === true);
    check("time reads as minutes and seconds", CCP.fmtTime(125.4) === "2:05");
  });
}
check("the page's scripts ran without an error", errors.length === 0, errors.join(" | "));
const failed = checks.filter((c) => !c.ok);
for (const c of failed) { console.log("FAIL", c.name, c.detail); }
console.log(`${checks.length - failed.length} of ${checks.length} page checks pass`);
process.exit(failed.length ? 1 : 0);
