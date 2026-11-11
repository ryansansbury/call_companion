"""The scorer matches items to key facts the way evals/score.py says, one to one."""
import unittest

from evals.score import closeness, prf, score_call

KEY = {"facts": [
    {"id": "k1", "field": "metrics", "value": "About $14,000 lost in one load", "number": 14000,
     "terms": ["fourteen thousand"], "segments": ["x-s002"]},
    {"id": "k2", "field": "pain", "value": "Nobody watches overnight", "terms": ["overnight", "watches"],
     "segments": ["x-s003"]}],
    "commitments": [], "absent": ["budget"]}


def item(iid, field, value, seg, quote, number=None):
    out = {"id": iid, "field": field, "value": value, "evidence": [{"segment": seg, "quote": quote}]}
    if number is not None:
        out["number"] = number
    return out


class Score(unittest.TestCase):
    def test_right_segment_and_number(self):
        self.assertGreater(closeness(item("i", "metrics", "$14,000 lost", "x-s002", "fourteen thousand", 14000),
                                     KEY["facts"][0]), 2)

    def test_wrong_number_does_not_match(self):
        self.assertEqual(closeness(item("i", "metrics", "$15,000 lost", "x-s002", "fourteen thousand", 15000),
                                   KEY["facts"][0]), 0)

    def test_wrong_field_does_not_match(self):
        self.assertEqual(closeness(item("i", "pain", "$14,000 lost", "x-s002", "fourteen thousand", 14000),
                                   KEY["facts"][0]), 0)

    def test_terms_match_without_the_segment(self):
        self.assertGreater(closeness(item("i", "pain", "Nobody watches it overnight", "x-s009", "nobody"),
                                     KEY["facts"][1]), 0)

    def test_each_side_on_its_own(self):
        # Two items holding the same fact are both right, and the fact is found once. A fact in the wrong field still
        # isn't found, and an item matching nothing is still wrong.
        a = item("a", "metrics", "$14,000 lost", "x-s002", "fourteen thousand", 14000)
        b = item("b", "metrics", "About $14,000", "x-s002", "fourteen thousand", 14000)
        c = item("c", "metrics", "$15,000 lost", "x-s002", "fourteen thousand", 15000)
        got = score_call([a, b, c], [], KEY)
        self.assertEqual((got["fields"]["metrics"]["tp"], got["fields"]["metrics"]["fp"]), (2, 1))
        self.assertEqual((got["fields"]["metrics"]["found"], got["fields"]["metrics"]["fn"]), (1, 0))
        self.assertEqual(got["fields"]["pain"]["fn"], 1)
        self.assertEqual(got["extra"], ["c"])
        self.assertEqual(got["not_found"], {"right": 1, "total": 1})

    def test_precision_and_recall_count_different_things(self):
        got = prf(2, 1, 1, found=1)
        self.assertEqual((got["precision"], got["recall"]), (0.667, 0.5))

    def test_prf(self):
        self.assertEqual(prf(3, 1, 1)["f1"], 0.75)


if __name__ == "__main__":
    unittest.main()
