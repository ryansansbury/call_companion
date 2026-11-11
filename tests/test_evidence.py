"""The evidence check passes real quotes and holds anything the call didn't say."""
import unittest

from engine import evidence

SEGS = {
    "d1-s004": {"id": "d1-s004", "text": "About $14,000 of seafood and dairy went straight into the dumpster."},
    "d1-s009": {"id": "d1-s009", "text": "We run forty trucks, well, 38 on the road right now."},
}


class Evidence(unittest.TestCase):
    def test_supported(self):
        item = {"value": "About $14,000 of seafood and dairy lost", "number": 14000,
                "evidence": [{"segment": "d1-s004", "quote": "about $14,000 of seafood and dairy"}]}
        self.assertEqual(evidence.check(item, SEGS), [])

    def test_quote_must_be_there(self):
        item = {"value": "A load lost", "evidence": [{"segment": "d1-s004", "quote": "a load of fish spoiled"}]}
        self.assertIn("the quote isn't in d1-s004", evidence.check(item, SEGS))

    def test_number_must_be_in_quote(self):
        item = {"value": "About $15,000 lost", "evidence": [{"segment": "d1-s004", "quote": "seafood and dairy"}]}
        self.assertTrue(any("15000" in p for p in evidence.check(item, SEGS)))

    def test_unknown_segment(self):
        item = {"value": "x", "evidence": [{"segment": "d1-s999", "quote": "x"}]}
        self.assertTrue(evidence.check(item, SEGS)[0].startswith("cites d1-s999"))

    def test_dates_skip_the_number_check(self):
        item = {"value": "Call on September 15", "evidence": [{"segment": "d1-s009", "quote": "38 on the road"}]}
        self.assertEqual(evidence.check(item, SEGS), [])

    def test_self_correction(self):
        item = {"value": "38 trucks on the road", "number": 38,
                "evidence": [{"segment": "d1-s009", "quote": "38 on the road right now"}]}
        self.assertEqual(evidence.check(item, SEGS), [])


if __name__ == "__main__":
    unittest.main()
