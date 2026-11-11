"""The claim checker backs what the call said and catches what it didn't, judged against the answer key."""
import unittest

from engine import claims
from tests.helpers import table

TABLES = {}


def judged(text, call="deal-3", approved=()):
    key = (call, tuple(approved))
    if key not in TABLES:
        TABLES[key] = table(call, approved)
    result = claims.check_email(text, TABLES[key])
    return [(c["text"], c["status"]) for s in result for c in s["claims"]]


def flagged(text, call="deal-3", approved=()):
    return [(t, s) for t, s in judged(text, call, approved) if s != "supported"]


class Numbers(unittest.TestCase):
    def test_clean_follow_up(self):
        got = judged("Thanks for your time today Linda. Year one comes to about $50,000, and we'll start with a "
                     "four-truck pilot for thirty days with a clean opt-out. I'll send the revised proposal with "
                     "net 45 terms by Thursday, and you'll decide by the thirtieth.")
        self.assertTrue(got, "found no claims")
        self.assertEqual([x for x in got if x[1] != "supported"], [], got)

    def test_wrong_number(self):
        self.assertIn(("$29,000", "unsupported"), judged("Hardware comes to $29,000 for the fleet."))

    def test_unit_must_match(self):
        self.assertEqual(flagged("About $500 a month covers five walk-ins.", call="s07"), [("five", "unsupported")])
        self.assertEqual(flagged("About $500 a month covers five vans and two walk-ins.", call="s07"), [])

    def test_real_number_on_the_wrong_thing(self):
        got = claims.check_email("That one load cost you about $5,000 in seafood and dairy.", table("deal-1"))
        c = got[0]["claims"][0]
        self.assertEqual((c["text"], c["status"], c["check"], c["fact"]), ("$5,000", "unsupported", "conflict", "d1f02"))
        self.assertIn("$14,000", c["reason"])

    def test_bare_one_is_not_a_claim(self):
        self.assertEqual(judged("Every one of your six vans gets a sensor on one dashboard.", call="s06"),
                         [("six", "supported")])


class Dates(unittest.TestCase):
    def test_wrong_date(self):
        self.assertEqual(judged("Installs start October 5."), [("October 5", "unsupported")])

    def test_right_date_other_call(self):
        got = judged("I'll send the invite for next Tuesday at ten.", call="deal-1")
        self.assertEqual([s for _, s in got], ["supported", "supported"])

    def test_swapped_date(self):
        got = claims.check_email("Priya will send the written pilot plan by Friday.", table("deal-2"))
        c = got[0]["claims"][0]
        self.assertEqual((c["status"], c["check"], c["fact"]), ("unsupported", "conflict", "d2f15"))
        self.assertIn("Thursday, September 17", c["reason"])

    def test_two_dates_one_sentence(self):
        self.assertEqual(flagged("Priya will send a written pilot plan for the four trucks by Thursday, and Tom "
                                 "will send the security questionnaire by Friday.", call="deal-2"), [])

    def test_past_weekday_is_not_a_date(self):
        self.assertEqual(judged("The walk-in died on a Saturday night and nobody knew until Sunday morning.",
                                call="s03"), [("Sunday", "supported")])


class Names(unittest.TestCase):
    def test_unknown_person(self):
        self.assertEqual(flagged("We'll bring Kevin from our install team to the technical call.", call="deal-1"),
                         [("Kevin", "unsupported")])

    def test_unknown_full_name(self):
        self.assertEqual(flagged("Angela will take it to Susan Park herself.", call="s01"),
                         [("Susan Park", "unsupported")])

    def test_ordinary_first_word(self):
        self.assertEqual(flagged("Losing a load like that hurts. Hardware is about $31,000.", call="deal-3"), [])

    def test_wrong_role(self):
        got = claims.check_email("Tom, your CFO, signs off on anything over $25,000.", table("deal-2"))
        c = [c for c in got[0]["claims"] if c["status"] != "supported"]
        self.assertEqual([(x["text"], x["check"]) for x in c], [("CFO", "role")])
        self.assertIn("IT manager", c[0]["reason"])

    def test_right_role(self):
        self.assertEqual(flagged("Linda Marsh, your CFO, makes the decision.", call="deal-3"), [])


class Promises(unittest.TestCase):
    def test_unapproved_concession(self):
        self.assertIn(("waive", "needs_approval"), judged("We'll waive the installation fee to keep you on schedule."))

    def test_approved_concession(self):
        self.assertEqual(flagged("We'll waive the installation.", approved=("d3k02",)), [])

    def test_invented_discount(self):
        got = judged("We can also take 20% off the software.")
        self.assertIn(("20%", "unsupported"), got)
        self.assertIn(("% off", "unsupported"), got)

    def test_feel_free_is_not_a_promise(self):
        self.assertEqual(flagged("Feel free to forward this to Linda."), [])

    def test_refund_rate_is_not_a_promise(self):
        self.assertEqual(flagged("Refunds on warm boxes hit about 3% of boxes.", call="s06"), [])


if __name__ == "__main__":
    unittest.main()
