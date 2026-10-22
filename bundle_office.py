"""Copy the installed LibreOffice runtime into a packaged desktop download."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def main() -> None:
    if sys.platform == "win32":
        source = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "LibreOffice"
        target = Path("dist/LocalFileConverter/LibreOffice")
        binary = target / "program/soffice.exe"
    elif sys.platform == "darwin":
        source = Path("/Applications/LibreOffice.app")
        target = Path("dist/LocalFileConverter.app/Contents/Resources/LibreOffice.app")
        binary = target / "Contents/MacOS/soffice"
    else:
        raise SystemExit("Bundled release is supported on Windows and macOS only.")
    if not source.is_dir():
        raise SystemExit(f"LibreOffice installation not found: {source}")
    shutil.copytree(source, target, symlinks=True)
    if not binary.is_file():
        raise SystemExit(f"LibreOffice binary missing from bundle: {binary}")
    print(f"Bundled LibreOffice: {binary}")


if __name__ == "__main__":
    main()
