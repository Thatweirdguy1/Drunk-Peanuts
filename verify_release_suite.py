"""Verify the packaged office modules can be imported without Python installed."""

import subprocess
import sys

if __name__ == "__main__":
    result = subprocess.run([sys.argv[1], "--office-self-check"], timeout=60, check=False)
    raise SystemExit(result.returncode)
