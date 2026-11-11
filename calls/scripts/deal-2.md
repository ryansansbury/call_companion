# Call 2, technical validation (Tuesday, September 15)

Marcus Webb (AE) and Priya Natarajan (SE) from Brinewatch, with Tom Becker (IT, IT manager) and Rachel Torres (OPS)
from Rhyolite Foodservice. About five minutes. The buyers do most of the talking. Marcus finally asks how the
decision gets made and who else is in the running, and Priya cuts Tom off once.

d2-001  AE    Morning, everyone. Thanks for joining. Rachel, Tom, this is Priya Natarajan, our sales engineer. Priya, over to you.
d2-002  SE    {pause 0.4} Thanks, Marcus. Tom, Rachel mentioned you'd rather skip the slides, so I'd love to start with your questions.
d2-003  IT    {pause 0.8} Good. My first question is what this has to touch. If it needs a hole in the firewall, we're going to have a long conversation. We've had vendors promise nothing touches our network and then ask for a VPN two weeks in.
d2-004  SE    {pause 0.5} It doesn't touch your network at all. Each truck gets a gateway on cellular, the warehouse gateway uses cellular too, and nothing on your side has to open a port.
d2-005  IT    {bc 3.0} Okay.
d2-006  IT    {pause 0.6} So the dock Wi-Fi never comes into it? Because the dock Wi-Fi is, let's say, a work in progress. Half the time the handhelds drop off it in the freezer.
d2-007  SE    {pause 0.4} Never. If a truck loses signal, the gateway stores the readings and sends them when it reconnects.
d2-008  IT    {pause 0.7} What about logins? I'm not managing another set of passwords. We already have six vendors with their own portals, and every time someone leaves, I'm the one chasing those accounts down.
d2-009  SE    {pause 0.4} We support single sign-on, so your people use the accounts they already have, and you turn someone off in one place.
d2-010  IT    {pause 0.8} And the data. Who owns it, where does it live, and how long do you keep it? Those three answers decide a lot for me.
d2-011  SE    {pause 0.5} You own it. It's stored in the United States, we keep two years of history by default, and you can export all of it whenever you want.
d2-012  OPS   {pause 0.6} Two years matters to us. Some customers ask for a full year of records, and I'd rather not be at the edge.
d2-013  IT    {pause 0.5} {cut 14} Okay. Then my other question is the routing software. Does this talk to it, or is it
d2-014  SE    It does. We send a nightly file, or we push each delivery's readings to the stop record through an API.
d2-015  IT    {pause 0.6} The nightly file is fine to start. I'd rather not open up the routing system to anyone until we've lived with this for a while.
d2-016  AE    {pause 0.7} Rachel, last week you said the alerts have to reach the right person fast. What does fast mean for you?
d2-017  OPS   {pause 0.8} Five minutes. Overnight we've only got one dispatcher, so if a unit drifts at two in the morning, dispatch should know within five minutes, and if nobody acknowledges it, it comes to me.
d2-018  SE    {pause 0.4} That's how escalation works. Dispatch and the driver get the first text, and if nobody acknowledges it in five minutes, it goes to the next person on the list.
d2-019  OPS   {pause 0.6} And the driver app has to work with no signal. Half our routes go through dead zones out past the county line, and the drivers can't sit around waiting for a bar of service.
d2-020  SE    {pause 0.4} It does. The app keeps logging and syncs later.
d2-021  AE    {pause 0.8} Can I ask how a decision like this gets made at Rhyolite? Who else weighs in besides the two of you?
d2-022  OPS   {pause 0.9} I make the recommendation. Tom has to sign off on security, and nothing gets past him without that. And anything over twenty-five thousand dollars goes to Linda Marsh, our CFO, for approval.
d2-023  AE    {pause 0.4} And the board?
d2-024  OPS   {pause 0.5} No, it doesn't go that far. Linda's the final word.
d2-025  AE    {pause 0.6} Got it. And is Brinewatch the only option you're looking at?
d2-026  OPS   {pause 1.1} We're also talking to Frostgauge. Their hardware came in about thirty percent cheaper, but they don't have a driver app, and that's a big deal for us.
d2-027  IT    {bc 2.4} Right.
d2-028  AE    {pause 0.6} That's helpful to know. So before any of this goes to Linda, what would you need to see?
d2-029  OPS   {pause 0.7} A pilot. A few trucks on real routes, ideally the ones with the worst dead zones, and alerts that actually show up at two in the morning.
d2-030  SE    {pause 0.5} We could do four trucks for thirty days, installed at your yard overnight, so no truck comes off the road.
d2-031  OPS   {pause 0.5} That works. Installs at night matter, because we can't pull trucks during the week. We're running every truck we have right now.
d2-032  IT    {pause 0.7} I'll need your security questionnaire filled out before anything gets installed. I can send ours over by Friday. It's long, so give yourselves some time.
d2-033  SE    {pause 0.4} Perfect. And I'll send you a written pilot plan for the four trucks by Thursday.
d2-034  AE    {pause 0.6} And Rachel, would you be up for bringing Linda to a call next week, once she's seen the plan?
d2-035  OPS   {pause 0.6} Yes. Next Tuesday at ten again. I'll bring Linda.
d2-036  AE    {pause 0.4} Great. I'll send the invite. Thanks, both of you. This was really useful.
d2-037  IT    {pause 0.3} Thanks.
