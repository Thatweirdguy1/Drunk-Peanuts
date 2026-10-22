"""Smoke-test the copied LibreOffice binary and its conversion filters."""

import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    binary = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="local-converter-office-smoke-") as folder:
        root = Path(folder)
        source = root / "check.txt"
        source.write_text("Bundled LibreOffice conversion check.\n", encoding="utf-8")
        result = subprocess.run(
            [str(binary), f"-env:UserInstallation=file:///{(root / 'profile').as_posix()}",
             "--headless", "--convert-to", "pdf", "--outdir", str(root), str(source)],
            capture_output=True, text=True, timeout=120,
        )
        output = root / "check.pdf"
        if result.returncode or not output.is_file() or output.read_bytes()[:4] != b"%PDF":
            raise SystemExit(f"Bundled LibreOffice conversion failed: {result.stderr or result.stdout}")
    print("Bundled LibreOffice conversion passed")


if __name__ == "__main__":
    main()
