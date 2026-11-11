/* The claim checker in the browser: the same rules as engine/claims.py, judged against the same table.

   The build writes each call's table (its checked facts with their dates, numbers and topic words, the names the
   call said, and each person's roles) and the shared word lists into data.js. This file parses the email and judges
   every claim. tests/vectors/claims.json holds the cases both versions must agree on, and tests/js/check_claims.js
   runs them. No network, no dependencies. */
(function (root) {
  "use strict";

  const SMALL = {zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
    eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17, eighteen: 18,
    nineteen: 19, twenty: 20, thirty: 30, forty: 40, fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90};
  const SCALES = {thousand: 1000, million: 1000000};
  const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
  const MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
    "november", "december"];
  const ORDINALS = {first: 1, second: 2, third: 3, fourth: 4, fifth: 5, sixth: 6, seventh: 7, eighth: 8, ninth: 9,
    tenth: 10, eleventh: 11, twelfth: 12, thirteenth: 13, fourteenth: 14, fifteenth: 15, sixteenth: 16,
    seventeenth: 17, eighteenth: 18, nineteenth: 19, twentieth: 20, thirtieth: 30};
  const UNIT_ORD = {first: 1, second: 2, third: 3, fourth: 4, fifth: 5, sixth: 6, seventh: 7, eighth: 8, ninth: 9};
  const DAYNUM = "(\\d{1,2}(?:st|nd|rd|th)?|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|" +
    "eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth|" +
    "thirtieth|(?:twenty|thirty)[- ](?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth))";
  const WEEKDAY = "(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)";
  const MONTH = "(?:january|february|march|april|may|june|july|august|september|october|november|december)";
  const DATE_SPAN = new RegExp("\\b(?:(?:next|this|by|on)\\s+)?" + WEEKDAY + "(?:\\s+the\\s+[a-z0-9-]+)?\\b|\\b" +
    MONTH + "\\s+(?:the\\s+)?[a-z0-9-]+\\b|\\bthe\\s+[a-z0-9-]+\\s+of\\s+" + MONTH + "\\b|\\bthe\\s+(?:\\d{1,2}" +
    "(?:st|nd|rd|th)|first|second|third|fourth|fifth|tenth|fifteenth|twentieth|thirtieth|" +
    "(?:twenty|thirty)[- ][a-z]+)\\b|\\btoday\\b|\\btomorrow\\b", "gi");
  const BOUNDARY = /(?<!\d),(?!\d)|[;:()]|\b(?:and|but|so|while|because|which|then)\b/gi;
  const NAME_TOKEN = /\b[A-Z][a-z]+(?:['’-][A-Za-z]+)*/g;
  const PERSON_BEFORE = /\b([A-Z][a-z]+)(?:\s+[A-Z][a-z]+)?(?:,\s+(?:(?:the|your|our|their|an?)\s+)?(?:(?!(?:and|or|but)\s)[a-z]+\s+){0,2}|\s+as\s+(?:(?:the|your|our|their|an?)\s+)?)$/;
  const PERSON_AFTER = /^,?\s+([A-Z][a-z]+)/;
  const DIGITS = /\$?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:\s*(k|thousand|million)\b)?\s*(%|percent)?/gi;
  const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);

  /* numbers.py */
  function wordsValue(tokens) {
    let total = 0, current = 0;
    for (const t of tokens) {
      if (t === "and") continue;
      if (own(SMALL, t)) current += SMALL[t];
      else if (t === "hundred") current = (current || 1) * 100;
      else if (own(SCALES, t)) { total += (current || 1) * SCALES[t]; current = 0; }
    }
    return total + current;
  }

  function spoken(text) {
    const low = text.toLowerCase().replace(/-/g, " ");
    const out = [];
    let run = [], start = null, end = null;
    const flush = () => {
      while (run.length && run[run.length - 1] === "and") run.pop();
      const scaleOnly = run.every(t => own(SCALES, t) || t === "hundred");
      if (run.some(t => t !== "and") && !(scaleOnly && /\d\s*$/.test(low.slice(0, start)))) {
        out.push([wordsValue(run), start, end]);
      }
      run = [];
    };
    for (const m of low.matchAll(/[a-z]+/g)) {
      const w = m[0];
      const isNum = own(SMALL, w) || w === "hundred" || own(SCALES, w);
      const joins = w === "and" && run.length && ["hundred", "thousand", "million"].includes(run[run.length - 1]);
      const lead = w === "a" && !run.length;
      if (isNum || joins) {
        if (!run.length) start = m.index;
        run.push(w);
        end = m.index + w.length;
        continue;
      }
      if (lead) {
        const nxt = low.slice(m.index + 1).replace(/^\s+/, "");
        if (nxt.startsWith("hundred") || nxt.startsWith("thousand")) {
          start = m.index; run = ["one"]; end = m.index + 1;
          continue;
        }
      }
      if (run.length) flush();
    }
    if (run.length) flush();
    return out;
  }

  function written(text) {
    const out = [];
    for (const m of text.matchAll(DIGITS)) {
      let value = parseFloat(m[1].replace(/,/g, ""));
      if (Number.isNaN(value)) continue;
      const scale = (m[2] || "").toLowerCase();
      value *= scale === "k" || scale === "thousand" ? 1000 : scale === "million" ? 1000000 : 1;
      out.push([value, m.index, m.index + m[0].length]);
    }
    return out;
  }

  /* dates.py */
  function dayNumber(text) {
    const t = text.toLowerCase().replace(/-/g, " ").trim();
    let m = /^(\d{1,2})(st|nd|rd|th)?$/.exec(t);
    if (m) return parseInt(m[1], 10);
    if (own(ORDINALS, t)) return ORDINALS[t];
    const parts = t.split(/\s+/);
    if (parts.length === 2 && (parts[0] === "twenty" || parts[0] === "thirty") && own(UNIT_ORD, parts[1])) {
      return (parts[0] === "twenty" ? 20 : 30) + UNIT_ORD[parts[1]];
    }
    return null;
  }

  function mkDate(y, m, d) {
    const x = new Date(Date.UTC(y, m - 1, d));
    return x.getUTCFullYear() === y && x.getUTCMonth() === m - 1 && x.getUTCDate() === d ? x : null;
  }
  const addDays = (d, n) => new Date(d.getTime() + n * 86400000);
  const weekday = d => (d.getUTCDay() + 6) % 7;
  const iso = d => d.toISOString().slice(0, 10);
  function parseIso(s) { const [y, m, d] = s.split("-").map(Number); return mkDate(y, m, d); }

  function inYear(day, month, dnum) {
    if (!dnum) return null;
    const d = mkDate(day.getUTCFullYear(), month, dnum);
    if (!d) return null;
    return d >= addDays(day, -60) ? d : mkDate(day.getUTCFullYear() + 1, month, dnum);
  }

  function resolve(phrase, day) {
    if (!phrase) return null;
    const t = " " + phrase.toLowerCase().replace(/,/g, " ") + " ";
    let m = /\b(\d{4})-(\d{2})-(\d{2})\b/.exec(t);
    if (m) return mkDate(+m[1], +m[2], +m[3]);
    if (/\btoday\b|\bthis afternoon\b|\bthis morning\b/.test(t)) return day;
    if (/\btomorrow\b/.test(t)) return addDays(day, 1);
    m = new RegExp("\\b(" + MONTHS.join("|") + ")\\s+(?:the\\s+)?" + DAYNUM + "\\b").exec(t);
    if (m) return inYear(day, MONTHS.indexOf(m[1]) + 1, dayNumber(m[2]));
    m = new RegExp("\\bthe\\s+" + DAYNUM + "\\s+of\\s+(" + MONTHS.join("|") + ")\\b").exec(t);
    if (m) return inYear(day, MONTHS.indexOf(m[2]) + 1, dayNumber(m[1]));
    m = new RegExp("\\bthe\\s+" + DAYNUM + "\\b").exec(t);
    if (m) {
      const dn = dayNumber(m[1]);
      if (dn) {
        let y = day.getUTCFullYear(), mo = day.getUTCMonth() + 1;
        if (dn < day.getUTCDate()) { mo += 1; if (mo === 13) { y += 1; mo = 1; } }
        return mkDate(y, mo, dn);
      }
    }
    m = new RegExp("\\b(?:next\\s+)?(" + DAYS.join("|") + ")\\b").exec(t);
    if (m) {
      const target = DAYS.indexOf(m[1]);
      if (new RegExp("\\bnext\\s+" + m[1]).test(t)) return addDays(day, 7 - weekday(day) + target);
      return addDays(day, ((target - weekday(day)) % 7 + 7) % 7 || 7);
    }
    return null;
  }

  /* claims.py */
  function make(lex) {
    const UNITS = lex.units, CURRENCY = new Set(lex.currency), STOP = new Set(lex.stop);
    const NUMBER_WORDS = new Set(lex.number_words), COMMON = new Set(lex.common);
    const DAYSET = new Set(DAYS), MONTHSET = new Set(MONTHS);
    const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const wordAt = (low, phrase) => [...low.matchAll(new RegExp("(?<![a-z])" + esc(phrase) + "(?![a-z])", "g"))];
    const same = (a, b) => Math.abs(a - b) < 1e-9;

    function sentences(text) {
      return (text || "").trim().split(/(?<=[.!?])\s+|\n+/).filter(p => p.trim());
    }
    const stem = w => (w.length > 3 && w.endsWith("s") && !w.endsWith("ss") ? w.slice(0, -1) : w);

    function topicWords(text) {
      const out = [];
      const low = (text || "").toLowerCase().replace(/’/g, "'");
      for (const m of low.matchAll(/[a-z]+(?:'[a-z]+)?/g)) {
        let w = m[0];
        if (w.endsWith("'s")) w = w.slice(0, -2);
        if (w.includes("'") || w.length < 3 || STOP.has(w) || own(UNITS, w) || NUMBER_WORDS.has(w) || DAYSET.has(w) ||
            MONTHSET.has(w)) continue;
        out.push(stem(w));
      }
      return out;
    }

    function clause(sentence, start, end, reach = 6) {
      let lo = 0, hi = sentence.length;
      for (const m of sentence.matchAll(BOUNDARY)) {
        if (m.index + m[0].length <= start) lo = m.index + m[0].length;
        else if (m.index >= end) { hi = m.index; break; }
      }
      const before = [...sentence.slice(lo, start).matchAll(/\S+/g)].slice(-reach).map(m => m[0]);
      const after = [...sentence.slice(end, hi).matchAll(/\S+/g)].slice(0, reach).map(m => m[0]);
      return [...before, sentence.slice(start, end), ...after].join(" ");
    }

    function unitAfter(text, end) {
      const m = /^\s*-?(%|[a-z]+(?:-[a-z]+)*)(?:\s+([a-z]+(?:-[a-z]+)*))?/.exec(text.slice(end).toLowerCase());
      if (!m) return null;
      const words = [m[1], m[2]];
      for (let i = 0; i < 2; i++) {
        const word = words[i];
        if (word === undefined) break;
        if (CURRENCY.has(word)) return "usd";
        if (own(UNITS, word)) return UNITS[word];
        if (i === 0 && (STOP.has(word) || NUMBER_WORDS.has(word))) break;
      }
      return null;
    }

    function dateClaims(text, day) {
      const found = [];
      for (const m of text.matchAll(DATE_SPAN)) {
        const before = text.slice(Math.max(0, m.index - 9), m.index).toLowerCase();
        if (/\b(?:a|last|every)\s+$/.test(before) && new RegExp("^" + WEEKDAY, "i").test(m[0])) continue;
        if (/^the\s+[a-z-]+$/i.test(m[0]) && !/\b(?:by|on|until|till|before|after|from|of|through)\s+$/.test(before)) {
          continue;
        }
        const d = resolve(m[0], day);
        if (d) found.push({kind: "date", text: m[0], start: m.index, end: m.index + m[0].length, value: iso(d)});
      }
      return found;
    }

    function numberClaims(text, skip) {
      const found = [];
      const spans = [...spoken(text), ...written(text)].sort((a, b) => a[1] - b[1]);
      for (const [value, s, e] of spans) {
        if (skip.some(([a, b]) => a <= s && s < b)) continue;
        const raw = text.slice(s, e).trim();
        const low = raw.toLowerCase();
        let unit;
        if (low.startsWith("$")) unit = "usd";
        else if (low.endsWith("%") || low.endsWith("percent")) unit = "percent";
        else unit = unitAfter(text, e);
        if (unit === null && value >= 1900 && value <= 2100) continue;
        if (unit === null && low === "one") continue;
        found.push({kind: unit === "usd" ? "money" : unit === "percent" ? "percent" : "count", text: raw, start: s,
          end: s + text.slice(s, e).trimEnd().length, value, unit});
      }
      return found;
    }

    function promiseClaims(text, policy) {
      const low = text.toLowerCase(), found = [];
      for (const [key, rule] of Object.entries(policy)) {
        const blocked = (rule.except || []).flatMap(x => wordAt(low, x).map(m => [m.index, m.index + m[0].length]));
        let hit = null;
        for (const w of rule.words) {
          for (const m of wordAt(low, w)) {
            if (!blocked.some(([a, b]) => a <= m.index && m.index + m[0].length <= b)) { hit = m; break; }
          }
          if (hit) break;
        }
        if (hit) {
          found.push({kind: "promise", text: text.slice(hit.index, hit.index + hit[0].length), start: hit.index,
            end: hit.index + hit[0].length, rule: key, label: rule.label});
        }
      }
      return found;
    }

    function nameKey(token) {
      const t = token.toLowerCase().replace(/’/g, "'");
      return t.endsWith("'s") ? t.slice(0, -2) : t;
    }

    function nameClaims(sentence, tbl) {
      const known = new Set(tbl.known), vocab = new Set(tbl.vocab);
      const lowerHere = new Set([...sentence.matchAll(/\b[a-z][a-z'-]*/g)].map(m => m[0]));
      const first = /^[\s"'(]*/.exec(sentence)[0].length;
      const runs = [];
      for (const m of sentence.matchAll(NAME_TOKEN)) {
        const last = runs.length ? runs[runs.length - 1] : null;
        if (last && sentence.slice(last[last.length - 1].index + last[last.length - 1][0].length, m.index) === " ") {
          last.push(m);
        } else runs.push([m]);
      }
      const flagged = [];
      for (const run of runs) {
        for (const m of run) {
          const key = nameKey(m[0]);
          if (known.has(key) || COMMON.has(key) || DAYSET.has(key) || MONTHSET.has(key) || NUMBER_WORDS.has(key) ||
              vocab.has(key) || lowerHere.has(key) || key.length < 3) continue;
          if (m.index === first && run.length === 1 && key === m[0].toLowerCase()) continue;
          const end = key !== m[0].toLowerCase() ? m.index + key.length : m.index + m[0].length;
          const last = flagged[flagged.length - 1];
          if (last && sentence.slice(last.end, m.index) === " ") {
            last.end = end;
            last.text = sentence.slice(last.start, end);
          } else flagged.push({kind: "name", start: m.index, end, text: sentence.slice(m.index, end)});
        }
      }
      for (const c of flagged) {
        Object.assign(c, {status: "unsupported", fact: null, check: "unknown_name",
          reason: `${c.text} isn't named anywhere in the call`});
      }
      return flagged;
    }

    function roleKeys(text) {
      const low = (text || "").toLowerCase();
      return Object.keys(lex.roles).filter(key => lex.roles[key].some(p => wordAt(low, p).length)).sort();
    }

    function roleMentions(text, people) {
      const low = text.toLowerCase(), out = [];
      for (const [key, phrases] of Object.entries(lex.roles)) {
        for (const p of phrases) {
          for (const m of wordAt(low, p)) {
            const who = personNear(text, m.index, m.index + m[0].length, people);
            if (who) out.push([who, key, m.index, m.index + m[0].length]);
          }
        }
      }
      return out;
    }

    function unitKeys(unit) {
      const out = [];
      for (const m of (unit || "").toLowerCase().matchAll(/%|[a-z]+(?:-[a-z]+)*/g)) {
        const key = CURRENCY.has(m[0]) ? "usd" : (own(UNITS, m[0]) ? UNITS[m[0]] : null);
        if (key && !out.includes(key)) out.push(key);
      }
      return out;
    }

    function datesIn(text, day) {
      return [...new Set(dateClaims(text || "", day).map(c => c.value))].sort();
    }

    function numberPairs(text) {
      const ds = dateClaims(text, mkDate(2026, 1, 1));
      const seen = new Set(), out = [];
      for (const c of numberClaims(text, ds.map(d => [d.start, d.end]))) {
        const k = c.value + "|" + c.unit;
        if (!seen.has(k)) { seen.add(k); out.push([c.value, c.unit]); }
      }
      return out;
    }

    /* engine/claims.py table(): the facts with their dates, numbers and topic words, the names the call said,
       the everyday words in it, and each person's roles. */
    function table(facts, dayIso, people, companies, transcript) {
      const day = parseIso(dayIso);
      const callText = [transcript || "", ...facts.map(f => f.value || ""), ...facts.flatMap(f => f.quotes || [])]
        .join("\n");
      const vocab = new Set([...callText.matchAll(/\b[a-z][a-z'-]*/g)].map(m => m[0]));
      const known = new Set();
      for (const p of people) for (const m of p.name.matchAll(/[A-Za-z]+/g)) known.add(m[0].toLowerCase());
      for (const c of companies) for (const m of c.matchAll(/[A-Za-z]+/g)) known.add(m[0].toLowerCase());
      for (const m of callText.matchAll(NAME_TOKEN)) known.add(nameKey(m[0]));
      const proper = [...new Set([...known].filter(k => !vocab.has(k) && !COMMON.has(k) && !k.includes("'"))
        .map(stem))].sort();
      const roles = {}, roleText = {};
      for (const p of people) {
        const keys = roleKeys(p.role);
        for (const m of p.name.matchAll(/[A-Za-z]+/g)) {
          const w = m[0].toLowerCase();
          roles[w] = roles[w] || new Set();
          keys.forEach(k => roles[w].add(k));
          if (p.role && !(w in roleText)) {
            const two = p.role.slice(0, 2);
            roleText[w] = /[A-Za-z]/.test(two) && two === two.toUpperCase() ? p.role :
              p.role[0].toLowerCase() + p.role.slice(1);
          }
        }
      }
      const names = new Set([...Object.keys(roles), ...[...known].filter(k => !vocab.has(k) && !COMMON.has(k))]);
      for (const [who, key, s, e] of roleMentions(callText, names)) {
        roles[who] = roles[who] || new Set();
        roles[who].add(key);
        if (!(who in roleText)) roleText[who] = callText.slice(s, e);
      }
      const rows = facts.map(f => {
        const text = [f.value || "", ...(f.quotes || [])].join(" ");
        const ds = new Set(datesIn(text, day));
        if (f.date) ds.add(f.date);
        const mine = numberPairs(f.value || "");
        if (f.number !== null && f.number !== undefined) {
          const us = unitKeys(f.unit);
          for (const u of (us.length ? us : [null])) {
            if (!mine.some(([v, x]) => v === f.number && x === u)) mine.push([f.number, u]);
          }
        }
        const pairs = mine.concat(numberPairs(text).filter(([v, u]) => !mine.some(([a, b]) => a === v && b === u)));
        const ownDates = new Set(datesIn(f.value || "", day));
        if (f.date) ownDates.add(f.date);
        const approved = f.approved !== undefined && f.approved !== null ? Boolean(f.approved) : f.kind !== "concession";
        return {id: f.id, field: f.field, value: f.value, kind: f.kind === undefined ? null : f.kind, approved,
          policy: f.policy === undefined ? null : f.policy, date: f.date === undefined ? null : f.date,
          dates: [...ds].sort(), pairs, own: mine, own_dates: [...ownDates].sort(),
          topic: [...new Set(topicWords(f.value))].sort(), text: text.toLowerCase()};
      });
      const sortedObj = o => Object.fromEntries(Object.keys(o).sort().map(k => [k, o[k]]));
      return {day: dayIso, facts: rows, known: [...known].sort(), vocab: [...vocab].sort(), proper,
        roles: sortedObj(Object.fromEntries(Object.entries(roles).map(([k, v]) => [k, [...v].sort()]))),
        role_text: sortedObj(roleText)};
    }

    function personNear(text, start, end, people) {
      let m = PERSON_BEFORE.exec(text.slice(0, start));
      if (m && people.has(m[1].toLowerCase())) return m[1].toLowerCase();
      m = PERSON_AFTER.exec(text.slice(end));
      if (m && people.has(m[1].toLowerCase())) return m[1].toLowerCase();
      return null;
    }

    function roleClaims(sentence, tbl) {
      const low = sentence.toLowerCase(), people = new Set(Object.keys(tbl.roles)), out = [];
      for (const [key, phrases] of Object.entries(lex.roles)) {
        for (const p of phrases) {
          for (const m of wordAt(low, p)) {
            const who = personNear(sentence, m.index, m.index + m[0].length, people);
            if (!who) continue;
            const has = tbl.roles[who] || [];
            if (has.length && !has.includes(key)) {
              out.push({kind: "role", text: sentence.slice(m.index, m.index + m[0].length), start: m.index,
                end: m.index + m[0].length, value: key, status: "unsupported", fact: null, check: "role",
                reason: `the call has ${who[0].toUpperCase() + who.slice(1)} as ${tbl.role_text[who]}`});
            }
          }
        }
      }
      return out;
    }

    const score = (f, topic, proper) => {
      let s = 0;
      for (const w of new Set(f.topic)) if (topic.has(w)) s += proper.has(w) ? 2 : 1;
      return s;
    };
    function best(facts, topic, proper) {
      let pick = null, top = -1;
      for (const f of facts) { const s = score(f, topic, proper); if (s > top) { pick = f; top = s; } }
      return pick;
    }

    function conflict(claim, sentence, tbl, sup, others, show) {
      if (!others.length) return null;
      const proper = new Set(tbl.proper);
      const topic = new Set(topicWords(clause(sentence, claim.start, claim.end)));
      const sBest = Math.max(...sup.map(f => score(f, topic, proper)));
      const rival = best(others, topic, proper);
      const c = score(rival, topic, proper);
      if (c >= 2 && c >= sBest + 2) {
        return Object.assign({}, claim, {status: "unsupported", fact: rival.id, check: "conflict",
          reason: `this is ${show(rival)} in the call (${rival.id})`});
      }
      return null;
    }

    const hasUnit = (f, unit) => wordAt(f.text, unit).length > 0 || wordAt(f.text, unit + "s").length > 0;
    const holds = (f, value, unit) => f.pairs.some(([v, u]) => same(v, value) &&
      (unit === null || u === unit || (u === null && hasUnit(f, unit))));

    function showNumber(value, unit) {
      const n = Number.isInteger(value) ? value.toLocaleString("en-US") : String(value);
      if (unit === "usd") return "$" + n;
      if (unit === "percent") return n + "%";
      if (unit === null) return n;
      return `${n} ${same(value, 1) ? unit : (lex.plural[unit] || unit + "s")}`;
    }
    function showDate(s) {
      const d = parseIso(s);
      const cap = w => w[0].toUpperCase() + w.slice(1);
      return `${cap(DAYS[weekday(d)])}, ${cap(MONTHS[d.getUTCMonth()])} ${d.getUTCDate()}`;
    }

    function supportedBy(claim, sentence, tbl, sup) {
      const topic = new Set(topicWords(clause(sentence, claim.start, claim.end)));
      const f = best(sup, topic, new Set(tbl.proper));
      return Object.assign({}, claim, {status: "supported", fact: f.id, check: null, reason: `matches ${f.id}`});
    }

    function judgeNumber(claim, sentence, tbl) {
      const sup = tbl.facts.filter(f => holds(f, claim.value, claim.unit));
      if (!sup.length) {
        return Object.assign({}, claim, {status: "unsupported", fact: null, check: "missing",
          reason: `no fact from the call has ${showNumber(claim.value, claim.unit)}`});
      }
      if (claim.unit !== null) {
        const others = tbl.facts.filter(f => !sup.includes(f) &&
          f.pairs.some(([v, u]) => u === claim.unit && !same(v, claim.value)));
        const show = f => showNumber(f.pairs.find(([v, u]) => u === claim.unit && !same(v, claim.value))[0],
          claim.unit);
        const hit = conflict(claim, sentence, tbl, sup, others, show);
        if (hit) return hit;
      }
      const mine = sup.filter(f => f.own.some(([v, u]) => same(v, claim.value) && (claim.unit === null || u === claim.unit)));
      return supportedBy(claim, sentence, tbl, mine.length ? mine : sup);
    }

    function judgeDate(claim, sentence, tbl) {
      if (claim.value === tbl.day) {
        return Object.assign({}, claim, {status: "supported", fact: null, check: null, reason: "the day of the call"});
      }
      const sup = tbl.facts.filter(f => f.dates.includes(claim.value));
      if (!sup.length) {
        return Object.assign({}, claim, {status: "unsupported", fact: null, check: "missing",
          reason: `no fact from the call is dated ${showDate(claim.value)}`});
      }
      const others = tbl.facts.filter(f => !sup.includes(f) && f.dates.length);
      const hit = conflict(claim, sentence, tbl, sup, others, f => showDate(f.date || f.dates[0]));
      if (hit) return hit;
      const mine = sup.filter(f => f.own_dates.includes(claim.value));
      return supportedBy(claim, sentence, tbl, mine.length ? mine : sup);
    }

    function judgePromise(claim, sentence, tbl, policy) {
      const words = policy[claim.rule].words;
      const skip = new Set(lex.generic);
      for (const r of Object.values(policy)) for (const w of r.words) if (/^[a-z]+$/.test(w)) skip.add(stem(w));
      const topic = new Set(topicWords(clause(sentence, claim.start, claim.end)).filter(w => !skip.has(w)));
      for (const f of tbl.facts) {
        if (f.kind !== "concession") continue;
        if (f.policy !== claim.rule && !words.some(w => wordAt(f.text, w).length)) continue;
        if (f.topic.some(w => !skip.has(w) && topic.has(w))) {
          if (f.approved) {
            return Object.assign({}, claim, {status: "supported", fact: f.id, check: null, reason: `approved, ${f.id}`});
          }
          return Object.assign({}, claim, {status: "needs_approval", fact: f.id, check: "approval",
            reason: `${claim.label.toLowerCase()} need a manager's approval first`});
        }
      }
      return Object.assign({}, claim, {status: "unsupported", fact: null, check: "promise",
        reason: "nobody offered this on the call"});
    }

    function checkEmail(text, tbl, policy) {
      policy = policy || lex.policy;
      const day = parseIso(tbl.day);
      const out = [];
      for (const s of sentences(text)) {
        const ds = dateClaims(s, day);
        const found = [...ds, ...numberClaims(s, ds.map(c => [c.start, c.end])), ...promiseClaims(s, policy)]
          .sort((a, b) => a.start - b.start);
        const judged = found.map(c => c.kind === "date" ? judgeDate(c, s, tbl) :
          c.kind === "promise" ? judgePromise(c, s, tbl, policy) : judgeNumber(c, s, tbl));
        const all = [...judged, ...nameClaims(s, tbl), ...roleClaims(s, tbl)].sort((a, b) => a.start - b.start);
        out.push({sentence: s, claims: all});
      }
      return out;
    }

    function approve(tbl, ids) {
      const set = new Set(ids);
      return Object.assign({}, tbl, {facts: tbl.facts.map(f => set.has(f.id) ? Object.assign({}, f, {approved: true}) : f)});
    }

    function summary(result) {
      const counts = {supported: 0, unsupported: 0, needs_approval: 0};
      for (const s of result) for (const c of s.claims) counts[c.status] += 1;
      return counts;
    }

    return {checkEmail, approve, summary, sentences, topicWords, showDate, showNumber, table};
  }

  const api = {make, resolve, spoken, written, iso, parseIso};
  root.CCClaims = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
