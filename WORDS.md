# Call Companion: every word on the page

Each `## key` starts an entry. Keys under `ui.` go to the page's script as they are. Lines that read
`- name = label` make a table.

## page.title
Call Companion

## page.line
A recorded sales call becomes CRM notes, a coaching scorecard, and a follow-up email. Every line is tied to the moment in the call that supports it.

## page.preview
Development preview. These calls have no audio yet, and the AI results come from a stand-in that answers from the answer key. Nothing on this page is a real result.

## page.pick
Call

## page.pick.deal
The deal

## page.pick.scored
The scored set

## page.model
Model

## page.present
Present

## page.tabs
- fields = Fields
- deal = Deal
- email = Email
- coach = Coach

## page.aria
- calls = The calls
- call = The call
- record = What the call produced
- panels = What to show
- screens = Which card to show

## page.screens
- calls = Calls
- call = Call
- record = Record

## page.recorded
Replaying recorded runs

## page.how
How it works

## page.back
Back to the calls

## page.footer.short
Every company, person, call, and number here is made up.

## page.footer
Every company, person, call, and number on this page is made up. The calls were scripted and voiced by text to speech, and the AI results are recorded runs that your browser replays without calling any service.

## page.byline
Built by Ryan Sansbury

## page.links
- site = ryansansbury.com
- code = Code on GitHub

## ui.call.length
{m} min {s} s

## ui.player.play
Play

## ui.player.pause
Pause

## ui.player.hint
Space plays and pauses, and the arrow keys skip five seconds.

## ui.player.noaudio
This preview has no audio yet. The playhead runs on a clock, and the transcript, the facts, and the chips still work.

## ui.player.loading
Loading the audio

## ui.player.speed
Speed

## ui.player.silent
Above 2× the call runs silent and the playhead keeps time.

## ui.replay.start
Replay the call

## ui.replay.all
Show everything

## ui.replay.note
Replaying the call. Each item appears once the line holding its quote has been said, and the recorded run itself read the whole call after it ended.

## ui.replay.notyet
Not heard yet

## ui.replay.email
The email gets drafted from the facts that passed the checks once the call ends.

## ui.replay.coach
The scorecard fills in when the call ends because every measure needs the whole call.

## ui.email.newsent
Added after the manager's approval

## ui.search.placeholder
Search the call

## ui.search.count
{n} matches

## ui.search.none
No matches

## ui.transcript.title
Transcript

## ui.transcript.cutoff
Mark words the transcriber was less than {p}% sure of

## ui.transcript.follow
Follow the audio

## ui.confirm.count
{n} facts to confirm with a person

## ui.confirm.one
One fact to confirm with a person

## ui.confirm.none
No fact needs a person at this cutoff

## ui.confirm.tag
Confirm with a person

## ui.confirm.why
The transcriber was unsure of a number or a name in this fact's quote. A person checks it before it reaches the CRM.

## ui.facts.title
What the call established

## ui.facts.empty
Not found in this call.

## ui.facts.more
The other fields

## ui.facts.held
Held by the evidence check

## ui.facts.heldnote
These came back from the model without support in the call. The page counts them as misses and never shows them as facts.

## ui.facts.by
Extracted by {model}. Every item quotes the transcript, and code checked each quote and each number before it appears here.

## ui.chip.play
Play this moment

## ui.fields
- metrics = Metrics
- economic_buyer = Economic buyer
- decision_criteria = Decision criteria
- decision_process = Decision process
- paper_process = Paper process
- pain = Identified pain
- champion = Champion
- competition = Competition
- critical_event = Critical event
- budget = Budget
- pricing = Pricing
- amount = Amount
- close_date = Close date
- next_steps = Next steps
- stakeholders = Stakeholders
- risks = Risks
- account = The account
- seller_claims = What the seller said
- commitments = Commitments

## ui.deal.title
The CRM record after {call}

## ui.deal.single
A scored call stands on its own. This record comes from this call alone.

## ui.deal.stage
Stage

## ui.deal.rules
The stage rules

## ui.deal.rulesnote
Each stage needs its own rules and every earlier stage's. Switch a rule off and the stage recomputes.

## ui.deal.ruleoff
Counting this rule

## ui.deal.approve
Approve the concession

## ui.deal.approvenote
Marcus floated waiving the installation, and a waived fee needs a manager's approval. Approving it lets the email repeat it and moves the deal into negotiation.

## ui.deal.changes
What changed on each call

## ui.deal.changes.none
This is the first call. Every field is new.

## ui.deal.record
The record

## ui.deal.payload
The payload

## ui.deal.payloadnote
The same record as a CRM would receive it. The keys are API names in the style of a Salesforce opportunity.

## ui.deal.steps
Next steps

## ui.deal.seller
Our commitments

## ui.deal.buyer
Their commitments

## ui.deal.waiting
Waiting on approval

## ui.deal.approved
Approved

## ui.deal.kept
Kept

## ui.deal.empty
Nothing yet

## ui.deal.first
First came up in {call}

## ui.email.title
The follow-up email

## ui.email.by
Drafted by {model} from the checked facts alone. Code then checked it sentence by sentence.

## ui.email.subject
Subject

## ui.email.edit
Edit the email

## ui.email.done
Done editing

## ui.email.reset
Back to the draft

## ui.email.samples
Add a bad claim

## ui.email.sample
- money = A wrong amount
- count = A wrong count
- percent = A wrong percent
- date = A wrong date
- name = A wrong name
- promise = A promise nobody made

## ui.email.summary
{n} claims checked with {ok} supported and {bad} flagged

## ui.email.findings
What the checker found

## ui.email.clean
Every number, date, name, and promise in this email comes from the call.

## ui.email.status
- supported = Supported
- unsupported = Unsupported
- needs_approval = Needs approval

## ui.email.approvedraft
This draft was written after the concession was approved.

## ui.email.leftout
Approval lets the email repeat the concession, but this model left it out. The prompt allows it and doesn't require it.

## ui.email.limits
The checker reads numbers, dates, names, roles, and promises against the facts the evidence check kept. It doesn't judge tone or paraphrased ideas, and a real number moved onto a fact that holds no number of its own can slip past it.

## ui.email.nodraft
No draft was recorded for this call with this model.

## ui.email.kind
- money = Amount
- percent = Percent
- count = Count
- date = Date
- name = Name
- role = Role
- promise = Promise

## ui.coach.title
Coaching scorecard

## ui.coach.rep
{name}, {role}

## ui.coach.score
Score

## ui.coach.outof
out of 100

## ui.coach.weights
Weights

## ui.coach.weightsnote
Move a weight and the score recomputes. The measures stay as the audio timed them.

## ui.coach.talk
Talk time

## ui.coach.deal
The rep across the three deal calls

## ui.coach.dealnote
Marcus talks most on the discovery call. On the technical call the buyers do most of the talking.

## ui.coach.note
The coaching note

## ui.coach.noteby
Written by {model} from the call and its numbers. Every point is tied to its moment.

## ui.coach.strengths
What went well

## ui.coach.improve
What to work on

## ui.coach.nonote
No coaching note was recorded for this call with this model.

## ui.coach.metrics
- talk_share = Rep's share of the talking
- longest_monologue_s = Rep's longest monologue
- longest_story_s = Buyer's longest story
- patience_s = Patience before answering
- questions = Questions asked
- questions_per_10min = Questions per ten minutes
- open_share = Share of open questions
- rep_interruptions = Times the rep talked over the buyer
- interactivity = Back and forth per five minutes
- next_step_quality = Next steps with an owner and a date

## ui.coach.defs
- talk_share = Each person's speaking time over everyone's. It comes from voice activity on each person's own track.
- longest_monologue_s = The rep's longest run of speech. The buyer's replies under two seconds don't break it.
- longest_story_s = The same measure for the buyer.
- patience_s = The median pause between the buyer finishing and the rep starting. Pauses over five seconds are left out.
- questions_per_10min = How many of the rep's sentences end in a question mark in ten minutes of call.
- open_share = Questions that ask the buyer to explain. Questions about a count, a name, or a date count as closed.
- rep_interruptions = The rep starting for more than a second while the buyer is mid-sentence.
- interactivity = Switches between the two sides per five minutes. Backchannels don't count, and the number stops at 10.
- next_step_quality = A next step counts when it has both an owner and a date.

## ui.coach.legend
- seller = Seller
- buyer = Buyer

## ui.coach.band
The shaded part of each bar is the good range, and the mark is this call.

## ui.coach.qs
The questions {name} asked

## ui.coach.qcount
{n} in this call

## ui.coach.qtag
- open = Open
- closed = Closed

## ui.deal.eyebrow
The deal

## ui.deal.sub
{n} calls from {first} to {last}

## ui.scored.eyebrow
The scored set

## ui.scored.sub
{n} shorter calls with other buyers. {m} stayed unseen until the prompts were frozen.

## ui.call.with
with {names}

## ui.call.people
{rep} with {others}

## ui.player.position
Position in the call

## ui.call.reached
Reached {stage}

## ui.split
- dev = Tuning
- test = Test

## ui.flags
- pain = Pain
- metrics = Metrics
- critical_event = Critical event
- amount = Price
- close_date = Close date
- budget = Budget
- competition = Competition
- decision_criteria = Criteria
- economic_buyer = Economic buyer
- next_steps = Next step
- concession = Concession

## ui.stair.title
The stage after each call

## ui.stair.note
Dashed lines are still ahead

## ui.stair.wait
Waits for approval

## ui.stair.close
Close {date}

## ui.stair.audit
Audit week

## ui.deal.notyet
Not set yet

## ui.deal.changed
What call {n} changed

## ui.deal.point
Point at one to find it in the call

## ui.deal.point.touch
Tap one to find it in the call

## ui.deal.more
{n} more changes from this call

## ui.deal.from
from {call}

## ui.deal.kind
- stage = Stage
- amount = Amount
- close_date = Close date
- next_step = Next step
- contact = New contact
- risk = Risk
- commitment = Commitment
- kept = Kept
- wait = Needs approval
- approved = Approved

## ui.email.to
To

## ui.how.code
The code behind this

## ui.present.next
Next

## ui.present.back
Back

## ui.present.exit
Exit

## ui.present.step
Step {n} of {total}

## ui.present.steps
- 1 = The pain in the buyer's own words
- 2 = Click a field and hear it said
- 3 = The deal changes call by call
- 4 = Plain rules set the stage
- 5 = A concession waits for approval
- 6 = The email comes from checked facts
- 7 = Type a promise and watch it caught
- 8 = Coaching from the audio's own timing
- 9 = Change what the score values
- 10 = The scoreboard with its misses
- 11 = Every model side by side
- 12 = The code behind each check

## ui.present.text
- 1 = Rachel describes the night a reefer unit died with a load of seafood and dairy on it. The transcript follows the audio, and the segment that's playing stays highlighted.
- 2 = Each field the model filled cites the words it came from. The Metrics chip plays the second Rachel puts a number on the loss, and code already confirmed that number is in the quote.
- 3 = The record builds across the three calls, and every change links to the moment that caused it. A new contact, a new risk, and a kept commitment each have their own line.
- 4 = The stage comes from plain conditions anyone can read. Switch a rule off and the stage recomputes in front of you.
- 5 = On the third call Marcus floats waiving the installation. A waived fee needs a manager's approval, and until someone gives it the email can't repeat the offer and the deal stays short of negotiation.
- 6 = The draft is written from the checked facts alone. Every number, date, and name in it is underlined and linked to the fact behind it.
- 7 = Each button adds a sentence with a planted mistake. The checker flags it as you watch and says why in plain words, and you can type your own.
- 8 = These numbers come from when each person actually spoke on their own track. The weak rep's calls sit beside the strong rep's in the scored set.
- 9 = The weights are a judgment call and they're yours to change. The score recomputes while the measures stay as the audio timed them.
- 10 = An answer key existed before any AI ran because the calls were written from it. This is how each model did against it on calls it never saw during tuning. Every miss is listed.
- 11 = The same prompts ran on each model. Accuracy, held items, cost per call, and time per call sit side by side, and the cheapest model that clears the bars answers the deal calls first.
- 12 = Every check on this page is a short function you can read. This is the claim checker. The same rules run in Python for the recorder and in JavaScript for the page.

## how.title
How it works

## how.lead
AI listens, code checks, and a person decides. A model reads the transcript and fills the CRM fields, and every item it returns quotes the words it came from. Code confirms each quote is really in the transcript and each number is in the quote, and it holds anything that fails. The follow-up email is written only from what passed, and a second check reads every number, date, name, and promise in it before anyone sends it.

## how.map.title
What's AI, what's code, and what's a person

## how.map
- audio = The calls|Scripted by hand and voiced line by line with a text to speech model|code
- stt = Transcription|Whisper on a laptop for each person's track with word timings and confidence|ai
- vad = Who spoke when|Voice activity measured on each person's track|code
- a1 = The CRM fields|A model reads the transcript and quotes its evidence|ai
- check = The evidence check|Each quote is in the transcript and each number is in its quote|code
- confirm = Uncertain words|Facts that hold a doubtful number or name go to a person|person
- crm = The record and the stage|Plain rules from a config file|code
- a2 = The follow-up email|A model writes from the checked facts alone|ai
- claims = The claim checker|Every number, date, name, and promise against the facts|code
- approve = Concessions|A manager approves anything off the price list|person
- coach = The scorecard|Measured from the timings with weights you set|code
- a3 = The coaching note|A model writes it from the call and the numbers|ai

## how.map.legend
- ai = AI step
- code = Code
- person = A person

## how.calls.title
How the calls were made

## how.calls
Every call started as an answer key that lists each fact the call has to hold. The script came second and says those facts the way people talk. People start over and cut each other off and answer with a short "right" or "yeah." A validator confirmed that every fact's words are actually spoken before anything was voiced. Each line was then voiced by a stock text to speech voice, and the buyer's side runs through a simulated phone line with a little noise to bring the transcriber's job closer to a real call.

The deal is three calls between Brinewatch and Rhyolite Foodservice. Brinewatch sells cold-chain monitoring, and Rhyolite is a regional food distributor with 38 trucks on the road. The nine scored calls are shorter. Two reps talk with nine different buyers, and the models never saw five of those calls until the prompts were frozen.

## how.calls.upper
Synthetic audio is easier than a real call. The voices are clean, nobody mumbles, and the scripts hold every fact on purpose. These scores are an upper bound on what the same pipeline would do on real recordings.

## how.score.title
The scoreboard

## how.score.lead
These scores compare each model's fields with the answer key. An item counts when it's in the right field, cites the moment the fact was said or uses its key words, and carries the right number. Precision asks how many of a model's items match a fact in the key, and recall asks how many of the key's facts some item matches. The test calls are the five the prompts never saw during tuning.

## how.score.none
The scores appear here once the recorded runs are in.

## how.score.cols
- model = Model
- split = Calls
- f1 = F1
- precision = Precision
- recall = Recall
- held = Held by the evidence check
- notfound = Empty fields left empty

## how.score.splits
- dev = Tuning (four calls)
- test = Test (five calls)
- deal = The deal (three calls)

## how.score.misses
What the routed model missed on the test calls

## how.compare.title
The models side by side

## how.compare.lead
The same frozen prompts ran on every model. The cost is what each call cost to process at the providers' list prices, and the monthly figure is an estimate at a thousand calls a month.

## how.compare.cols
- model = Model
- f1 = F1 on test
- held = Held
- flagged = Email claims flagged
- cost = Cost per call
- month = At 1,000 calls a month
- time = Seconds per call

## how.compare.thinking
Both Claude models think before they answer. Across the twelve calls Haiku wrote six times as many thinking tokens as Sonnet, and that's why it takes longer here.

## how.compare.flags
A flagged claim asks a person to look before the email goes out. Any number the facts don't hold gets flagged, and that includes a harmless count a model adds on its own like "two concerns."

## how.compare.route
The page answers the deal calls with {model}. It's the cheapest model that cleared the bars on the tuning calls.

## how.compare.best
The page answers the deal calls with {model}. No model reached an F1 of {bar} on the tuning calls, and this one came closest.

## how.compare.local
The local model ran on the same Mac as the transcriber and nothing about these calls left the machine. It answered with its thinking mode off because one step with it on ran past ten minutes. Its row shows what that privacy costs in accuracy.

## how.checker.title
Testing the claim checker

## how.checker
The test set holds {planted} bad claims across six kinds and {clean} fair follow-up emails, and all of them were written before the checker was scored. The checker caught {caught} of the planted claims and raised a false alarm in {alarms} of the fair emails.

## how.checker.miss
The miss is a real number moved onto the wrong thing. The call says half the routes cross dead zones, and a planted sentence says 30% of them do. That 30% is real, but it's the competitor's price gap from the same call. The routes fact holds no number and the checker has nothing to compare.

## how.checker.kinds
- money = Amounts
- count = Counts
- percent = Percentages
- date = Dates
- name = Names and roles
- promise = Promises

## how.audio.title
Transcription and timing

## how.audio
Each person is recorded and transcribed on their own track. The word error rate compares each transcript with the words the script actually said once both write numbers the same way. Talk time comes from voice activity on each track, and it's checked against the mixer's record of exactly when every line played.

## how.audio.bar
{within} of {total} calls land within two points of the true talk time. The voice activity settings were chosen on the four scored calls used for tuning and then checked on the other eight.

## how.audio.none
The transcription results appear here once the audio is made.

## how.audio.cols
- call = Call
- overall = Word error rate
- seller = Seller's side
- phone = Buyer on the phone line
- clean = Buyer before the phone line
- talk = Talk time off by

## how.questions.title
Testing the question count

## how.questions
Every question the reps ask in the twelve scripts was labeled open or closed by hand, and the rule that sorts them agrees with those labels on {agree} of {n} questions. The first version of the rule agreed on {first}. The revision came after reading every disagreement, and the newer figure is optimistic for that reason.

## how.runs.title
The recorded runs

## how.runs
The AI steps ran on my machine and were recorded. This page replays those recordings without calling any service. What you see is exactly what each model returned on the day it ran.

## how.runs.cols
- model = Model
- step = Step
- calls = Calls
- date = Recorded

## how.runs.steps
- extract = CRM fields
- followup = Follow-up email
- followup-approved = Email after approval
- coach = Coaching note

## how.privacy.title
Privacy

## how.privacy
Transcription runs on a laptop and the audio never leaves it. The text steps ran on cloud models through my own accounts. This page itself makes no network request beyond its own files.

## how.privacy.local
One run used a local model on the same machine to show what keeping everything at home costs in accuracy.

## how.limits.title
What it can't do

## how.limits
The calls are scripted and voiced by text to speech. They're cleaner than real ones. The claim checker reads numbers, dates, names, roles, and promises and doesn't judge tone or paraphrase. The coaching measures count what can be timed and counted, and a good call can still score low on a number. This is a demonstration of a method and not a product, and nothing here was tested on real calls.

## how.code.title
The code

## how.code
These are the project's real files as the build copied them into the page. The featured ones are the checks the page relies on most.

## how.code.tree
Files

## how.code.feat
- engine/claims.py = The claim checker
- engine/evidence.py = The evidence check
- engine/crm.py = The CRM record and stage rules
- engine/coaching.py = The coaching measures
- evals/score.py = The scorer
