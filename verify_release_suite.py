"""Verify the packaged office modules can be imported without Python installed."""

import subprocess
import sys

if __name__ == "__main__":
    for flag in ("--office-self-check", "--watchit-self-check"):
        result = subprocess.run([sys.argv[1], flag], timeout=90, check=False)
        if result.returncode:
            raise SystemExit(result.returncode)
