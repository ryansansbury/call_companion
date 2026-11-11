"""Spoken and written numbers read the same way, so a quote and a value agree on what number they hold."""
import unittest

from engine import numerals as n


class SpokenNumbers(unittest.TestCase):
    def test_words(self):
        cases = {
            "About fourteen thousand dollars of seafood": [14000],
            "Installation is about forty-five hundred.": [4500],
            "twelve hundred and sixty dollars a month": [1260],
            "We run forty trucks, well, thirty-eight on the road": [40, 38],
            "anything over forty-one degrees gets refused": [41],
            "about thirty percent cheaper": [30],
            "over five hundred hours a year": [500],
            "anything over twenty-five thousand dollars": [25000],
            "about thirty-one thousand dollars": [31000],
            "a hundred trucks": [100],
            "and then we left": [],
        }
        for text, want in cases.items():
            self.assertEqual(n.numbers(text), want, text)

    def test_digits(self):
        self.assertEqual(n.numbers("a 14,000 dollar write-off"), [14000])
        self.assertEqual(n.numbers("1,260 a month and 30% off"), [1260, 30])
        self.assertEqual(n.numbers("about 4.5k"), [4500])

    def test_has(self):
        self.assertTrue(n.has("Fourteen thousand dollars of seafood", 14000))
        self.assertTrue(n.has("It cost $14,000.", 14000))
        self.assertFalse(n.has("Fourteen trucks", 14000))
        self.assertTrue(n.has("We run forty trucks, well, thirty-eight on the road", 38))


if __name__ == "__main__":
    unittest.main()
