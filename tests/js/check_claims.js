/* Run site/claims.js on tests/vectors/claims.json and compare with what engine/claims.py returned.

     node tests/js/check_claims.js

   Exits 1 on the first disagreement, printing the case. */
"use strict";
const fs = require("fs");
const path = require("path");
const here = path.resolve(__dirname, "..", "..");
const C = require(path.join(here, "site", "claims.js"));
const v = JSON.parse(fs.readFileSync(path.join(here, "tests", "vectors", "claims.json"), "utf8"));

function canon(x) {
  if (Array.isArray(x)) return x.map(canon);
  if (x && typeof x === "object") {
    const out = {};
    for (const k of Object.keys(x).sort()) out[k] = canon(x[k]);
    return out;
  }
  return x;
}

const checker = C.make(v.lexicon);
let bad = 0, claims = 0;
const built = {};
for (const [name, x] of Object.entries(v.inputs)) {
  let t = checker.table(x.facts, x.day, x.people, x.companies, x.transcript);
  if (x.approved.length) t = checker.approve(t, x.approved);
  const a = JSON.stringify(canon(t)), b = JSON.stringify(canon(v.tables[name]));
  if (a !== b) {
    bad += 1;
    console.log("TABLE MISMATCH", name);
    const ta = canon(t), tb = canon(v.tables[name]);
    for (const k of Object.keys(tb)) {
      if (JSON.stringify(ta[k]) !== JSON.stringify(tb[k])) {
        console.log("  key", k);
        if (Array.isArray(tb[k])) {
          for (let i = 0; i < tb[k].length; i++) {
            if (JSON.stringify(ta[k][i]) !== JSON.stringify(tb[k][i])) {
              console.log("    python", JSON.stringify(tb[k][i]).slice(0, 400));
              console.log("    js    ", JSON.stringify((ta[k] || [])[i]).slice(0, 400));
              break;
            }
          }
        } else console.log("    python", JSON.stringify(tb[k]).slice(0, 300), "\n    js    ", JSON.stringify(ta[k]).slice(0, 300));
      }
    }
    if (bad > 2) process.exit(1);
  }
  built[name] = t;
}
for (const c of v.cases) {
  const got = checker.checkEmail(c.text, built[c.table]);
  const a = JSON.stringify(canon(got)), b = JSON.stringify(canon(c.result));
  claims += c.result.reduce((n, s) => n + s.claims.length, 0);
  if (a !== b) {
    bad += 1;
    console.log("MISMATCH", c.table, JSON.stringify(c.text));
    console.log("  python", b);
    console.log("  js    ", a);
    if (bad > 3) break;
  }
}
for (const d of v.dates) {
  const r = C.resolve(d.phrase, C.parseIso(d.day));
  const got = r ? C.iso(r) : null;
  if (got !== d.value) { bad += 1; console.log("DATE MISMATCH", d.phrase, d.day, "python", d.value, "js", got); }
}
if (bad) { console.log(`${bad} disagreements`); process.exit(1); }
console.log(`Python and JavaScript agree on ${Object.keys(v.inputs).length} tables, ${v.cases.length} cases, ${claims} claims and ${v.dates.length} dates`);
