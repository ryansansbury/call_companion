# Decisions

What was decided and why, and every place a number was tuned after it was seen.

## The method

- **The answer key comes first.** Each call spec lists its facts before its script exists, and a validator proves
  every fact's words are spoken. Without that order there's no honest way to score extraction.
- **Three freezes.** The key, the planted claims, the clean emails, and the configs freeze before any model runs. The
  key lined up with the transcripts freezes next. The prompts and the scoring code freeze after the tuning calls, and
  the recorder refuses the test and deal calls until they do. `evals/freeze.py --check` shows any change since.
- **One refreeze after the runs, for wording only (11/10).** The note in `calls/cast.json` was reworded to say only
  what the cast holds. No voice, line, or fact changed, and `evals/frozen.json` keeps the old hashes in its history.
- **Tuning calls and test calls.** Four scored calls tune the prompts and five stay unseen until the freeze. The
  three deal calls are scored too, and they're the ones the page opens on.
- **Recorded runs only.** The page never calls a model. The AI steps run on my machine and the build replays and
  validates each one again.
- **The local model sat out the launch.** Qwen 3.8 with 27 billion parameters thinks before it answers unless it's
  told not to. Its first extraction on my Mac took four and a half minutes and wrote 8,261 tokens for an answer of
  about 2,800. The follow-up after it thought for more than ten minutes and the recorder stopped waiting. The setup
  now turns its thinking off and asks it one short question before a long run. Even then the twelve calls would have
  held the launch for most of an hour, and the plan's cut order names the local run second. The page compares the
  three cloud models, and the one thinking run sits outside the build.

## The audio

- **Kokoro-82M** voices every line with stock voices that its license allows publishing. No voice is cloned.
- **One track per person.** Lines are voiced alone and placed on their speaker's track from the script's marks for
  pauses, overlaps, cut-offs, and backchannels. The buyers' tracks run through a phone-line filter with light noise.
- **Whisper large-v3-turbo through mlx-whisper** runs on each stretch of speech that voice activity found. Its word
  confidence drives the transcript's dotted underlines.
- **Each line is trimmed to its voice before the mix.** The voice model pads every line with half a second or more of
  silence. When lines were placed whole the padding sat on top of every scripted pause. Turns came almost a second apart and the
  ground truth counted the silence as talk. The mixer now keeps each line from just before its first sound to just
  after its last, and every call came out 8 to 12 percent shorter.
- **The voice activity settings were calibrated on the tuning calls.** The first settings put the speech bar 15 dB
  over each track's quietest tenth. The phone line's hiss raises that floor and the bar sat 8 dB higher on the
  buyers' tracks. That tilted talk time toward the seller. Four settings were chosen on the four tuning calls alone and
  the other eight were checked afterward. A held-out call that misses the two-point bar stays listed as a limit just as
  the claim checker's miss does.
- **The transcriber starts from the account's names.** The first transcription wrote the competitor Frostgauge three
  different ways, and the CRM would have held three competitors where the deal has one. Whisper now starts each call
  with the seller, the account, the competitor on file, and the people on the call, the same list a deployment would
  pull from the CRM and the calendar invite. Anyone a call only mentions stays off the list. A name like that can
  still come back misheard, and "counsel" heard as "council" stays the transcription error it is.
- **A fact is placed when its moment is found.** The aligner first stopped on any key word the transcript wrote
  another way. Most of those were the comparison's own fault. Whisper splits "$5,000" into "$5" and ",000" and
  writes "October 2nd" for "October second" and the comparison now reads both alike. A word the transcriber truly got wrong leaves its
  fact placed and scorable because scoring credits the moment an item cites. The misheard words are reported.
- **AAC fetched whole into a blob.** The site's host answers a byte-range request with the whole file, and Safari
  needs ranges to seek streamed audio. Playing from memory makes seeking exact everywhere.

## The checks

- **Values carry numbers as digits.** The extraction prompt asks for digits in each value, and the evidence check
  reads only digits there. A dry run showed number words in a value ("year one" and "no one") read as the number 1
  and holding good items.
- **"Next Wednesday" means the following week.** On a Tuesday it's eight days out. Every date in the twelve keys
  agrees with that rule.
- **The claim checker grew after the planted set was written.** Writing the 30 planted claims showed the spec needed
  names, roles, and real numbers on the wrong thing. Those checks came before the first scored run, and that run
  caught 29 of 30 with no false alarm in 12 clean emails. Two planted sentences also drew a stray flag for "the first
  season" read as a date. It was a real bug and the fix left the scores unchanged.
- **The extraction prompt was revised once on the tuning calls.** Claude Sonnet's first round scored F1 0.77 on the
  four tuning calls from a precision of 0.70 and a recall of 0.85. Its items merged two numbered facts into one or split one
  fact in two, filed facts in a neighboring field, cited the rep's recap instead of the first mention, and added
  impressions of mood. The revision added three rules (one fact per item, quote where it was first said, and record
  only what was said) and sharpened four field definitions. The next round freezes the prompts only if it scores at
  least as well, and evals/tuning_rounds.json keeps both.
- **The scorer judges each side on its own.** The revised prompt's round scored 0.744 under the first scorer, and
  that scorer paired items and facts one to one. The round left 31 items unmatched. 18 restated part of a fact the
  key already matched, 9 sat at a key fact's moment in a neighboring field, and 4 were true facts the key doesn't
  list. One-to-one pairing counted a fact written as two items twice against the model. Precision now asks whether
  each item matches some key fact and recall asks whether some item matches each fact. The rules for a match are
  the same as before. Round 2 scores 0.81 on
  the tuning calls that way, and the prompts froze on it. Round 1's replies weren't kept and can't be rescored.
  Neither round reaches the plan's bar of 0.85, and the page says so when no model clears it.
- **The miss stays.** "About 30% of your routes cross dead zones" puts a real number from the call on a fact that
  holds no number of its own. Nothing conflicts and the checker passes it. It stays in the planted set and the page
  lists it as a limit.
- **The open-question rule was revised after its errors were seen.** The first rule agreed with the hand labels on
  78% of 73 questions. It called counts and people open ("how many" and "who") and missed open questions behind a
  leading clause. The revision agrees on 97%. It was written after reading every disagreement, and the page calls
  that figure optimistic.

## The page

- **The light theme** uses the site's paper, ink, and teal. The speaker lanes use a teal and an orange that pass the
  palette validator on both surfaces, and every lane carries its name.
- **Everything visible lives in WORDS.md.** The build fails on a missing entry or a never-word.
- **The claim checker builds its own table in the browser** from the facts, the people, and the transcript, the
  same way the Python one does. That keeps the page light, and the parity test compares the tables as well as the
  verdicts.

## The workspace

- **Three cards in place of tabs.** Five mockups tried other shapes because the first page shared its layout with my
  other two demos. The one kept puts the calls, the call, and the record side by side on the paper with the same width
  and the same gap on either side. Below 1360 pixels the calls narrow to a strip of numbers, and below 901 pixels the
  three cards become screens to swipe between.
- **Threads tie every output to its line.** A curve runs from each item that has evidence to the transcript line it
  quotes. A line out of view gets a dashed end at the pane's edge, and those ends fan out in order. Pointing at either
  end lights both, and a phone uses the time chips the same way.
- **The replay never shows a fact early.** A fact counts as said once its first quote has ended in its line. Checks
  and fields the call met wait for their fact, a field the call hasn't set shows what the last call left, and the
  email and the scorecard wait for the end. The page says the model read each whole call after it ended.
- **A stage move cites the rule met last.** The first version cited the first newly met rule in config order, and
  it said call 3 reached Proposal at the budget line about a minute in. The rules weren't all met until the close
  date near the end. The build now times each fact by the same rule the replay uses and cites the one said last, and
  the change list and the replay now agree.
- **The stand-in quotes the line that best matches a fact.** It's the no-model backend that dry runs use. It used to
  quote the first line holding a fact's key words. That put two of call 3's facts on an earlier mention and dated
  the CFO's decision by the wrong phrase. It also lowered the first letter of a name. The page labels every stand-in
  result in red, and none of them ship.
- **Motion is optional.** Reduced motion in the reader's settings turns off every draw, glide, and highlight, and
  the page reads the same without them.
- **Approval marks only the sentence that uses the concession.** The first version marked each sentence of the
  approved draft that the first draft didn't hold word for word. The model writes the approved draft again from the
  start, and on the real runs nearly every sentence came back reworded and marked. A mark now goes only on a sentence
  that cites an approved concession. Sonnet's approved draft for call 3 leaves the waiver out. The prompt allows
  that and the page says so under the draft.
- **A sample bad claim goes in before the sign-off.** Sonnet signs its drafts with no full stop after the name. A
  sample added at the end ran into the signature and the checker read the two as one sentence, and it missed the
  wrong role there that it catches in the sentence alone. The page now adds a sample above the sign-off.
