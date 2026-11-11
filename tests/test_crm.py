"""The CRM record, the stage rules and the deal's change log, built from the answer key."""
import unittest

from agents import inputs
from engine import crm, diff
from tests.helpers import facts_from_key, spec

CALLS = ["deal-1", "deal-2", "deal-3"]


def deal(approved=()):
    return crm.deal([(c, facts_from_key(c)) for c in CALLS], approved=approved,
                    roster=inputs.roster(spec("deal-1")))


class Stage(unittest.TestCase):
    def test_the_deal_moves_a_stage_each_call(self):
        self.assertEqual([r["stage"] for r in deal()], ["Qualified", "Technical validation", "Proposal"])

    def test_approval_reaches_negotiation(self):
        self.assertEqual(deal(approved=("d3k02",))[-1]["stage"], "Negotiation")

    def test_switching_a_rule_off_recomputes(self):
        first = deal()[0]
        cfg = crm.load()
        self.assertEqual(crm.stage(first["checks"], cfg, off={"process"}), "Technical validation")
        self.assertEqual(crm.stage(first["checks"], cfg, off={"pain"}), "Qualified")

    def test_a_scored_call_stands_alone(self):
        rec = crm.record(facts_from_key("s02"), roster=inputs.roster(spec("s02")))
        self.assertEqual(rec["stage"], "Discovery")
        self.assertFalse([c for c in rec["checks"] if c["id"] == "metric"][0]["met"])


class Record(unittest.TestCase):
    def test_single_values_take_the_newest_call(self):
        last = deal()[-1]["fields"]
        self.assertEqual(last["amount"]["value"], 50000)
        self.assertEqual(last["close_date"]["value"], "2026-10-02")
        self.assertIn("revised proposal", last["next_step"]["value"])

    def test_restated_facts_merge(self):
        metrics = deal()[-1]["fields"]["metrics"]
        merged = [m for m in metrics if m.get("replaces")]
        self.assertIn(("d3f02", "d1f04"), [(m["fact"], m["replaces"]) for m in merged])
        self.assertEqual(len(metrics), 4)

    def test_contact_roles(self):
        got = {c["name"]: c["role"] for c in deal()[-1]["fields"]["stakeholders"]}
        self.assertEqual(got["Linda Marsh"], "Economic buyer")
        self.assertEqual(got["Rachel Torres"], "Champion")

    def test_payload_uses_api_names(self):
        p = crm.payload(deal()[-1])
        self.assertEqual((p["StageName"], p["Amount"], p["CloseDate"]), ("Proposal", 50000, "2026-10-02"))
        self.assertIn("Linda Marsh", [c["Name"] for c in p["OpportunityContactRoles"]])


class Changes(unittest.TestCase):
    def test_every_change_kind_shows_up(self):
        recs = deal()
        kinds = set()
        for i, r in enumerate(recs):
            kinds |= {c["kind"] for c in diff.changes(recs[i - 1] if i else None, r, spec(CALLS[i])["date"])}
        self.assertTrue({"stage", "amount", "close_date", "next_step", "contact", "risk", "commitment", "kept",
                         "fact"} <= kinds, kinds)

    def test_the_cfo_meeting_is_kept(self):
        recs = deal()
        kept = [c for c in diff.changes(recs[1], recs[2], "2026-09-22") if c["kind"] == "kept"]
        self.assertEqual([c["fact"] for c in kept], ["d2k03"])

    def test_restated_fact_is_not_new(self):
        recs = deal()
        facts = [c["fact"] for c in diff.changes(recs[1], recs[2], "2026-09-22")]
        self.assertNotIn("d3f02", facts)

    def test_a_stage_move_cites_the_rule_met_last(self):
        recs = deal()
        names = [s["name"] for s in crm.load()["stages"]]
        was, now = names.index(recs[1]["stage"]), names.index(recs[2]["stage"])
        before = {c["id"] for c in recs[1]["checks"] if c["met"]}
        fresh = [c for c in recs[2]["checks"] if c["met"] and c["fact"] and c["id"] not in before
                 and was < names.index(c["stage"]) <= now]
        self.assertGreater(len(fresh), 1)

        def cited(said=None):
            when = (lambda fact, call: said.get(fact)) if said else None
            return [c for c in diff.changes(recs[1], recs[2], "2026-09-22", when=when) if c["kind"] == "stage"][0]["fact"]

        self.assertEqual(cited(), fresh[0]["fact"])
        self.assertEqual(cited({c["fact"]: float(i) for i, c in enumerate(fresh)}), fresh[-1]["fact"])
        self.assertEqual(cited({c["fact"]: float(-i) for i, c in enumerate(fresh)}), fresh[0]["fact"])


if __name__ == "__main__":
    unittest.main()
