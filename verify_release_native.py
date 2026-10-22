"""Exercise packaged in-process Office conversion."""

import subprocess
import sys
import tempfile
from pathlib import Path


if __name__ == "__main__":
    executable = sys.argv[1]
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        source = root / "input.txt"
        source.write_text("Native conversion check", encoding="utf-8")
        odt = root / "output.odt"
        output = root / "again.txt"
        for first, second in ((source, odt), (odt, output)):
            subprocess.run([executable, "--convert", str(first), str(second)], check=True, timeout=60)
        if "Native conversion check" not in output.read_text(encoding="utf-8"):
            raise SystemExit("Packaged document round trip failed")
    print("Packaged native Office conversion passed")
