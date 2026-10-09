"""Unit tests for skills/work-humanizer/check.py. Run: python -m unittest discover tests"""
import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "check", Path(__file__).resolve().parent.parent / "skills" / "work-humanizer" / "check.py")
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)


def flags(text):
    return "\n".join(check.check(text))


class CheckTest(unittest.TestCase):
    def test_dashes_and_semicolons(self):
        out = flags("The release — finally — shipped; users noticed.")
        self.assertIn("em/en dashes: 2", out)
        self.assertIn("semicolons: 1", out)

    def test_stock_vocabulary_and_marketing(self):
        out = flags("We delve into a vibrant tapestry that will seamlessly empower your team.")
        self.assertIn("AI words", out)
        self.assertIn("delve", out)
        self.assertIn("marketing words", out)

    def test_pause_and_point_contrast_and_closer(self):
        out = flags("Here's the thing: it's not just a tool, but a partner. The bottom line is speed. Thoughts?")
        self.assertIn("Here's the thing", out)
        self.assertIn("not just a tool, but", out)
        self.assertIn("Thoughts?", out)

    def test_filler_transition_and_hedge(self):
        out = flags("The API is fast. Additionally, it is arguably cheaper.")
        self.assertIn("Additionally", out)
        self.assertIn("arguably", out)

    def test_bold_label_start(self):
        self.assertIn("bold-label starts: 1", flags("**Speed.** The new engine is faster."))

    def test_uniform_short_rhythm(self):
        out = flags("It works. It ships. It scales. It sells. It wins. It lasts.")
        self.assertIn("uniform: merge short ones", out)
        self.assertIn("openers", out)

    def test_plain_text_is_quiet(self):
        text = ("We cut no-shows from 18% to 7% in six months by switching to two-way texts. "
                "Patients reschedule by replying, which saved the front desk about 11 hours a week. "
                "Sopot only got to 12%, and nobody knows why yet.")
        self.assertEqual(flags(text), f"words: {len(text.split())}")


if __name__ == "__main__":
    unittest.main()
