"""The owner's writing rule of 11/16 on the page's words and the README, when the private lint is here. The public copy
doesn't carry tools/, so it skips there. A named product is fine on the page, so the lint's resume warnings pass."""
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
LINT = HERE.joinpath("tools", "lint_copy.py")


class WritingRule(unittest.TestCase):
    def test_the_page_and_the_readme_pass_the_lint(self):
        if not LINT.exists():
            self.skipTest("the lint stays private")
        for name in ("WORDS.md", "README.md"):
            done = subprocess.run([sys.executable, str(LINT), "--strict", name], cwd=str(HERE), capture_output=True, text=True)
            lines = done.stdout.splitlines()
            real = [ln for ln in lines if ln.startswith(name) and "is a claim his resume retired" not in ln.replace("; ", "\n").splitlines()[-1]
                    and not all("resume retired" in part for part in ln.split(": ", 1)[1].split("; "))]
            self.assertEqual(real, [], "\n".join(lines[-6:]))


if __name__ == "__main__":
    unittest.main()
