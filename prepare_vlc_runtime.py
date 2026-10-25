"""Regenerate VLC's cache after PyInstaller copies plugins and changes their mtimes."""

import os
import subprocess
import sys
from pathlib import Path


def prepare(package: Path, generator: Path | None = None):
    plugins = package.resolve() / "_internal/vlc_runtime/plugins"
    generator = generator or Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "VideoLAN/VLC/vlc-cache-gen.exe"
    if not plugins.is_dir() or not any(plugins.rglob("*_plugin.dll")):
        raise RuntimeError(f"VLC plugins are missing: {plugins}")
    if not generator.is_file():
        raise RuntimeError(f"VLC cache generator is missing: {generator}")
    subprocess.run([str(generator), str(plugins)], check=True, timeout=90,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    cache = plugins / "plugins.dat"
    if not cache.is_file() or cache.stat().st_size < 32:
        raise RuntimeError("VLC did not produce a usable plugin cache")
    print(f"Prepared VLC cache: {cache}")


if __name__ == "__main__":
    prepare(Path(sys.argv[1]))
