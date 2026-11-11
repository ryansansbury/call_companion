"""Evening out a script and a transcript before they're compared, and joining the pieces Whisper splits off."""
import unittest

from engine import align, segments


class Canon(unittest.TestCase):
    def test_a_thousands_comma_joins_even_with_a_space_before_it(self):
        self.assertEqual(align.canon("about $5 ,000 a month"), align.canon("about five thousand a month"))
        self.assertEqual(align.canon("under 20 ,000"), "under 20000")

    def test_ordinals_read_as_numbers_either_way(self):
        self.assertEqual(align.canon("October 2nd"), align.canon("October second"))
        self.assertEqual(align.canon("by the 30th"), align.canon("by the thirtieth"))
        self.assertEqual(align.canon("the 1st of November"), align.canon("the first of November"))
        self.assertEqual(align.canon("the twenty-first"), "the 21")


class Terms(unittest.TestCase):
    def test_a_hyphen_or_a_space_inside_a_long_term_still_finds_it(self):
        self.assertEqual(align.has_terms("we also do airport pick-ups twice a week", ["airport pickups"]), [])
        self.assertEqual(align.has_terms("Frost Gauge came in a lot cheaper", ["Frostgauge"]), [])

    def test_a_misheard_word_stays_missing(self):
        self.assertEqual(align.has_terms("I'll make sure Council has it", ["counsel"]), ["counsel"])
        self.assertEqual(align.has_terms("we're also talking to Frostgodge", ["Frostgauge"]), ["Frostgauge"])

    def test_a_short_term_needs_its_own_word(self):
        self.assertEqual(align.has_terms("the starter kit", ["art"]), ["art"])


class Joined(unittest.TestCase):
    def test_pieces_that_open_with_punctuation_join_the_word_before(self):
        words = [{"w": w, "start": i, "end": i + 1, "p": p} for i, (w, p) in
                 enumerate([("about", 0.9), ("$5", 0.8), (",000", 0.6), ("30", 0.9), ("%", 0.95), ("pick", 0.9),
                            ("-ups", 0.7), ("in", 0.9), ("-", 0.5), ("I", 0.9)])]
        out = segments.joined(words)
        self.assertEqual([w["w"] for w in out], ["about", "$5,000", "30%", "pick-ups", "in", "-", "I"])
        self.assertEqual(out[1]["p"], 0.6)
        self.assertEqual((out[1]["start"], out[1]["end"]), (1, 3))


if __name__ == "__main__":
    unittest.main()
