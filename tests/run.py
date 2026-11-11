"""Every check the build relies on, in one command.

    python3 tests/run.py

The unit tests, then the JavaScript claim checker against the Python one on the shared vectors, then the page's
click-through once the page is built. Exits 1 if anything fails.
"""
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))


def main():
    ok = True
    suite = unittest.defaultTestLoader.discover(str(HERE.joinpath("tests")))
    ok &= unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful()
    for script in ("check_claims.js", "check_app.js"):
        path = HERE.joinpath("tests", "js", script)
        if not path.exists():
            continue
        if script == "check_app.js" and not HERE.joinpath("site", "data.js").exists():
            print("check_app.js: skipped until the build writes site/data.js")
            continue
        ok &= subprocess.run(["node", str(path)], cwd=HERE).returncode == 0
    print("All checks pass." if ok else "Something failed.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
