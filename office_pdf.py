"""PDF export through an installed desktop office application."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from pypdf import PdfReader


MICROSOFT_FORMATS = {"docx": "WINWORD.EXE", "xlsx": "EXCEL.EXE", "pptx": "POWERPNT.EXE"}
LIBREOFFICE_FORMATS = {"docx", "xlsx", "pptx", "odt", "ods", "odp", "rtf"}
_external_launch_lock = threading.Lock()


def _office_executable(extension: str) -> Path | None:
    if sys.platform != "win32" or extension not in MICROSOFT_FORMATS:
        return None
    name = MICROSOFT_FORMATS[extension]
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if base:
            path = Path(base) / "Microsoft Office" / "root" / "Office16" / name
            if path.is_file():
                return path
    return None


def _libreoffice_executable() -> Path | None:
    for name in ("soffice.com", "soffice"):
        found = shutil.which(name)
        if found:
            return Path(found)
    candidates = (
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "LibreOffice/program/soffice.com",
        Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
    )
    return next((path for path in candidates if path.is_file()), None)


def available_engines(source: Path) -> list[str]:
    extension = source.suffix.lower().lstrip(".")
    engines = ["built-in"]
    if _office_executable(extension):
        engines.append("microsoft")
    if extension in LIBREOFFICE_FORMATS and _libreoffice_executable():
        engines.append("libreoffice")
    return engines


def resolve_engine(source: Path, requested: str) -> str:
    available = available_engines(source)
    if requested == "auto":
        return next((engine for engine in ("microsoft", "libreoffice", "built-in") if engine in available))
    if requested not in available:
        raise RuntimeError(f"{requested} PDF export is unavailable for {source.suffix}; install the application or choose another engine.")
    return requested


def _microsoft_pdf(source: Path, output: Path) -> None:
    try:
        import pythoncom
        import win32com.client
    except ImportError as error:
        raise RuntimeError("Microsoft Office automation support is unavailable in this build.") from error
    extension = source.suffix.lower().lstrip(".")
    program = {"docx": "Word.Application", "xlsx": "Excel.Application", "pptx": "PowerPoint.Application"}[extension]
    pythoncom.CoInitialize()
    application = document = None
    try:
        application = win32com.client.DispatchEx(program)
        if extension == "docx":
            application.DisplayAlerts = 0
            document = application.Documents.Open(str(source), ReadOnly=True, AddToRecentFiles=False)
            document.SaveAs2(str(output), FileFormat=17)
        elif extension == "xlsx":
            application.DisplayAlerts = False
            document = application.Workbooks.Open(str(source), UpdateLinks=0, ReadOnly=True)
            document.ExportAsFixedFormat(0, str(output))
        else:
            document = application.Presentations.Open(str(source), ReadOnly=True, Untitled=False, WithWindow=False)
            document.SaveAs(str(output), 32)
    finally:
        if document is not None:
            try:
                document.Close(False) if extension == "xlsx" else document.Close()
            except Exception:
                pass
        if application is not None:
            try:
                application.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def _libreoffice_pdf(source: Path, output: Path, workdir: Path) -> None:
    executable = _libreoffice_executable()
    if executable is None:
        raise RuntimeError("LibreOffice is not installed.")
    profile = (workdir / "profile").as_uri()
    command = [str(executable), f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pdf",
               "--outdir", str(workdir), str(source)]
    environment = os.environ.copy()
    if getattr(sys, "frozen", False):
        for key in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH"):
            original = environment.pop(f"{key}_ORIG", None)
            if original is None:
                environment.pop(key, None)
            else:
                environment[key] = original
    with _external_launch_lock:
        # PyInstaller changes Windows DLL lookup for bundled modules. Its lookup
        # must be suspended only while an external process inherits the setting.
        if sys.platform == "win32" and getattr(sys, "frozen", False):
            import ctypes
            ctypes.windll.kernel32.SetDllDirectoryW(None)
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, shell=False, env=environment)
        finally:
            if sys.platform == "win32" and getattr(sys, "frozen", False):
                ctypes.windll.kernel32.SetDllDirectoryW(sys._MEIPASS)
    try:
        stdout, stderr = process.communicate(timeout=180)
    except subprocess.TimeoutExpired as error:
        process.kill()
        process.communicate()
        raise RuntimeError("LibreOffice PDF export timed out.") from error
    generated = workdir / f"{source.stem}.pdf"
    if process.returncode or not generated.is_file():
        raise RuntimeError(f"LibreOffice PDF export failed (exit {process.returncode}): {(stderr or stdout).strip()[-400:]}")
    if generated != output:
        generated.rename(output)


def export_pdf(source: Path, target: Path, engine: str) -> None:
    """Export to a fresh target without replacing the source or an existing PDF."""
    source = Path(source).resolve(strict=True)
    target = Path(target).resolve()
    if target.suffix.lower() != ".pdf" or target.exists() or source == target:
        raise FileExistsError("Choose a new PDF output path.")
    engine = resolve_engine(source, engine)
    if engine == "built-in":
        raise ValueError("Built-in PDF export belongs to the native converter.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="freeconvert-pdf-") as temporary:
        workdir = Path(temporary)
        output = workdir / "export.pdf"
        if engine == "microsoft":
            _microsoft_pdf(source, output)
        else:
            _libreoffice_pdf(source, output, workdir)
        if not output.is_file() or not PdfReader(str(output)).pages:
            raise RuntimeError(f"{engine} did not produce a valid PDF.")
        created = False
        try:
            with target.open("xb") as destination:
                created = True
                with output.open("rb") as generated:
                    shutil.copyfileobj(generated, destination)
        except Exception:
            if created:
                target.unlink(missing_ok=True)
            raise
