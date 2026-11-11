"""README.md and the numbers in docs/CHEAT_SHEET.md, written by the build from the same results the page shows.

The prose lives here and follows the writing rules. The tables come from the bundle's results, so the README can't
drift from the page. A development preview writes nothing, since its numbers come from the stand-in.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
LIVE = "https://www.ryansansbury.com/call-companion/"

INTRO = """# Call Companion

A recorded sales call becomes CRM notes, a coaching scorecard, and a follow-up email. Every field the AI fills cites
the words it came from and the second they were said. Code confirms each quote and each number before anything is
shown, and a claim checker reads every number, date, name, and promise in the follow-up against the call.

[Open the demo]({live})
{hero}
Every company, person, call, and number here is made up. The calls were scripted from an answer key and voiced by
stock text to speech voices. The answer key existed before any AI step ran.

## What it shows

- **Every output is tied to its source line.** A thread runs from each field, change, email claim, and coaching
  measure to the transcript line it came from. Point at either end to light it.
- **Replay a call and watch the record build itself.**
  Each fact lands the moment its quote has been said, the stage steps up when its rules are met, and the email and
  scorecard fill in when the call ends.
- **Click a CRM field and hear the buyer say it.** Each fact carries chips that play its moment in the call.
- **Type a promise into the follow-up and watch it caught.** The checker runs in the browser as you type.
- **The deal changes call by call.** Three calls move one opportunity through plain stage rules you can switch
  off, and a staircase shows the stage after each call against the close date.
- **Coaching from the audio's own timing.** Talk time, monologues, patience, and questions come from each person's
  track, and the weights are yours to set.
- **An honest scoreboard.** Every model is scored against the answer key on calls it never saw during tuning, and
  the misses are listed.

{screens}## The AI map

| Step | Who does it | How it's checked |
|---|---|---|
| Transcription | Whisper large-v3-turbo on a laptop for each person's track | Word error rate against the scripts |
| Who spoke when | Voice activity on each track (code) | Talk time against the mixer's record |
| The CRM fields | A model that quotes its evidence | Each quote must be in the transcript and each number in the quote |
| Uncertain words | A person | Facts with a doubtful number or name go to "Confirm with a person" |
| The record and stage | Rules in `config/crm.json` (code) | Tests |
| The follow-up email | A model working from the checked facts alone | The claim checker in Python and in the page |
| Concessions | A manager | Nothing off the price list reaches the email until it's approved |
| The scorecard | Code with weights you set | Tests and the question rule against hand labels |
| The coaching note | A model | Every point must quote its moment |

## Results

{results}

## How the calls were made

Each call began as a list of the facts it has to hold, and the script came second. A validator confirms every fact's
words are actually spoken before anything is voiced. Kokoro-82M voices each line on its own speaker's track, and the
buyer's side runs through a simulated phone line with light noise. The deal is three calls between
Brinewatch and Rhyolite Foodservice. Brinewatch sells cold-chain monitoring, and Rhyolite is a regional food
distributor. The nine scored calls pair two reps with nine buyers, and five of them stayed unseen until the prompts
were frozen.

Synthetic audio is easier than a real call. These scores are an upper bound on what the same pipeline would do on
real recordings.

## Privacy

Transcription runs locally and the audio never leaves the machine. The text steps ran on cloud models through my own
accounts, and the page replays those recorded runs without calling any service.

## Running it

```
bash owner/bootstrap.sh                    # Python 3.12, Kokoro, mlx-whisper, ffmpeg, espeak-ng
bash owner/make_audio.sh                   # voice, mix and encode the calls
bash owner/transcribe.sh                   # transcribe each track
bash owner/record_ai_runs.sh --split dev   # record the AI steps
python3 build.py                           # build the page in site/ from what's on disk
python3 tests/run.py                       # the tests, the parity check and the page click-through
```

`python3 build.py --dev-preview` builds a labeled preview from the scripts alone without audio or a model.

## License

PolyForm Noncommercial 1.0.0. See LICENSE.
"""


def pct(x, d=0):
    return "" if x is None else f"{x * 100:.{d}f}%"


def dec(x):
    return "" if x is None else f"{x:.2f}"


def results_md(data):
    res = data["results"]
    labels = {m["id"]: m["label"] for m in data["models"]}
    rows = ["| Model | Calls | F1 | Precision | Recall | Held |", "|---|---|---|---|---|---|"]
    for m in [x["id"] for x in data["models"]]:
        for s, name in (("test", "Test (5)"), ("deal", "The deal (3)"), ("dev", "Tuning (4)")):
            v = (res["scores"].get(m) or {}).get(s)
            if v:
                rows.append(f"| {labels.get(m, m)} | {name} | {dec(v['f1'])} | {dec(v['precision'])} | "
                            f"{dec(v['recall'])} | {pct(v['unsupported_rate'], 1)} |")
    out = "\n".join(rows) if len(rows) > 2 else "The scores appear here once the recorded runs are in."
    comp = res["comparison"]
    if comp["rows"]:
        out += "\n\n| Model | Cost per call | At 1,000 calls a month (estimate) | Seconds per call |\n|---|---|---|---|\n"
        out += "\n".join(f"| {r['label']} | ${r['cost_per_call']:.4f} | ${r['per_month_estimate']:.2f} | "
                         f"{r['seconds_per_call']:.1f} |"
                         for r in sorted(comp["rows"], key=lambda r: r["model"] != comp["route"]))
    c = res.get("claims")
    if c:
        out += (f"\n\nThe claim checker caught {c['caught']} of {c['planted']} planted bad claims and raised a false "
                f"alarm in {c['false_alarm_emails']} of {c['clean_emails']} fair emails.")
    w = res.get("wer")
    if w:
        out += (f" Word error rate was {pct(w['overall'], 1)} overall. Buyers came to {pct(w['buyer_phone'], 1)} on "
                f"the phone line and {pct(w['buyer_clean'], 1)} before it.")
    return out


# The README's screens, taken by owner/browser_check.py at 1600 by 1000 and copied into docs/images/ once reviewed.
SHOTS = (("fields", "The Discovery call with each field tied to the line it came from"),
         ("deal", "The deal after call 3 as it waits for a manager's approval"),
         ("email", "The follow-up with a wrong amount added and flagged"),
         ("coach", "The coaching scorecard from the call's own timing"))


def gallery():
    """(the hero image under the intro, the screens section), each empty until docs/images/ holds its files."""
    have = {n: alt for n, alt in SHOTS if HERE.joinpath("docs", "images", f"{n}.png").exists()}
    hero = f"\n![{have['fields']}](docs/images/fields.png)\n" if "fields" in have else ""
    rest = [f"{alt}.\n\n![{alt}](docs/images/{n}.png)\n" for n, alt in SHOTS[1:] if n in have]
    return hero, ("## Screens\n\n" + "\n".join(rest) + "\n" if rest else "")


def write(data):
    if data["preview"]:
        return None
    hero, screens = gallery()
    text = INTRO.format(live=LIVE, results=results_md(data), hero=hero, screens=screens)
    HERE.joinpath("README.md").write_text(text, encoding="utf-8")
    return len(text)
