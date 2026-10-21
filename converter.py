"""Local file conversion. External tools run without a shell and never replace inputs."""

from __future__ import annotations

import csv
import io
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile
from pathlib import Path

import imageio_ffmpeg
import pillow_heif
import pypdfium2 as pdfium
import rawpy
from docx import Document
from openpyxl import Workbook, load_workbook
from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError
from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from pypdf import PdfReader
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

pillow_heif.register_heif_opener()
Image.MAX_IMAGE_PIXELS = 100_000_000

IMAGE = {"jpg", "jpeg", "png", "heic", "heif", "tif", "tiff", "gif", "bmp", "webp", "svg", "cr2", "nef", "arw", "ico"}
RASTER = {"jpg", "png", "webp", "tiff", "bmp", "gif", "ico", "pdf"}
VIDEO = {"mp4", "mov", "avi", "mpeg", "mpg", "mkv", "webm"}
AUDIO = {"mp3", "wav", "aiff", "m4a", "aac", "flac", "ogg"}
OFFICE = {"doc", "docx", "ppt", "pptx", "xls", "xlsx", "odt", "ods", "odp", "rtf"}
OFFICE_OUTPUT = {"pdf", "docx", "odt", "pptx", "odp", "xlsx", "ods", "txt"}
FFMPEG_VIDEO = {"mp4", "mov", "avi", "mpeg", "mkv", "webm", "gif", "mp3", "wav", "m4a", "aac", "flac", "ogg"}
FFMPEG_AUDIO = {"mp3", "wav", "aiff", "m4a", "aac", "flac", "ogg"}


def kind(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    if suffix in IMAGE:
        return "Image"
    if suffix == "pdf":
        return "PDF"
    if suffix in VIDEO:
        return "Video"
    if suffix in AUDIO:
        return "Audio"
    if suffix in OFFICE:
        return "Document"
    if suffix == "csv":
        return "Spreadsheet"
    if suffix == "txt":
        return "Text"
    return "Unsupported"


def available_formats(path: Path) -> list[str]:
    ext = path.suffix.lower().lstrip(".")
    group = kind(path)
    if group == "Image":
        choices = RASTER | {"svg"} if ext == "svg" else RASTER
    elif group == "PDF":
        choices = {"png", "jpg", "webp", "txt"}
    elif group == "Video":
        choices = FFMPEG_VIDEO
    elif group == "Audio":
        choices = FFMPEG_AUDIO
    elif ext == "csv":
        choices = {"xlsx", "txt"}
    elif ext == "xlsx":
        choices = {"csv", "pdf", "ods"} if shutil.which("soffice") or shutil.which("libreoffice") else {"csv"}
    elif ext == "docx":
        choices = {"txt"} | ({"pdf", "odt", "rtf"} if office_binary() else set())
    elif group == "Document":
        choices = OFFICE_OUTPUT if office_binary() else set()
    elif ext == "txt":
        choices = {"pdf"}
    else:
        choices = set()
    return sorted(choices - {ext})


def office_binary() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def ffmpeg_binary() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(command: list[str], timeout: int = 900) -> None:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, shell=False)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout)[-700:].strip() or "Converter failed")


def _image(path: Path) -> Image.Image:
    ext = path.suffix.lower().lstrip(".")
    if ext == "svg":
        data = path.read_bytes()
        root = ET.fromstring(data)
        if any(value and not value.startswith("#") for node in root.iter() for key, value in node.attrib.items() if key.endswith("href")):
            raise ValueError("SVG files with external resources are not supported.")
        renderer = QSvgRenderer(QByteArray(data))
        if not renderer.isValid():
            raise ValueError("Invalid SVG file.")
        size = renderer.defaultSize()
        picture = QImage(max(1, size.width()), max(1, size.height()), QImage.Format_ARGB32)
        picture.fill(0)
        painter = QPainter(picture)
        renderer.render(painter)
        painter.end()
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        picture.save(buffer, "PNG")
        return Image.open(io.BytesIO(bytes(buffer.data())))
    if ext in {"cr2", "nef", "arw"}:
        with rawpy.imread(str(path)) as raw:
            return Image.fromarray(raw.postprocess(use_camera_wb=True))
    return Image.open(path)


def _save_image(source: Path, target: Path, fmt: str) -> None:
    with _image(source) as opened:
        frame = ImageOps.exif_transpose(opened)
        if fmt == "pdf":
            images = [ImageOps.exif_transpose(f.copy()).convert("RGB") for f in ImageSequence.Iterator(frame)]
            images[0].save(target, "PDF", save_all=True, append_images=images[1:])
        elif fmt == "gif" and getattr(frame, "n_frames", 1) > 1:
            frames = [f.copy().convert("RGBA") for f in ImageSequence.Iterator(frame)]
            frames[0].save(target, "GIF", save_all=True, append_images=frames[1:], duration=opened.info.get("duration", 100), loop=opened.info.get("loop", 0))
        else:
            if fmt in {"jpg", "bmp"}:
                background = Image.new("RGB", frame.size, "white")
                if frame.mode == "RGBA":
                    background.paste(frame, mask=frame.getchannel("A"))
                else:
                    background.paste(frame.convert("RGB"))
                frame = background
            frame.save(target, {"jpg": "JPEG", "tiff": "TIFF"}.get(fmt, fmt.upper()))


def _pdf_to_image(source: Path, target: Path, fmt: str) -> None:
    pdf = pdfium.PdfDocument(str(source))
    try:
        if any(target.with_name(f"{target.stem}-{index + 1}{target.suffix}").exists() for index in range(1, len(pdf))):
            raise FileExistsError("A numbered PDF page output already exists.")
        # Multi-page image exports use numbered files alongside the selected first-page name.
        for index in range(len(pdf)):
            page = pdf[index]
            image = page.render(scale=2).to_pil()
            output = target if index == 0 else target.with_name(f"{target.stem}-{index + 1}{target.suffix}")
            if fmt == "jpg":
                image = image.convert("RGB")
            image.save(output, {"jpg": "JPEG"}.get(fmt, fmt.upper()))
            page.close()
    finally:
        pdf.close()


def _office(source: Path, target: Path, fmt: str) -> None:
    binary = office_binary()
    if not binary:
        raise RuntimeError("Install LibreOffice to convert this document format.")
    with tempfile.TemporaryDirectory(prefix="local-converter-") as tmp:
        # Independent profile avoids conflicts with an already-open LibreOffice instance.
        _run([binary, f"-env:UserInstallation=file:///{Path(tmp).as_posix()}/profile", "--headless", "--convert-to", fmt, "--outdir", tmp, str(source)])
        generated = Path(tmp) / f"{source.stem}.{fmt}"
        if not generated.exists():
            raise RuntimeError("LibreOffice did not produce an output file.")
        shutil.copy2(generated, target)


def _csv_to_xlsx(source: Path, target: Path) -> None:
    book = Workbook(write_only=True)
    sheet = book.create_sheet("Sheet1")
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.reader(stream):
            sheet.append(row)
    book.save(target)


def _xlsx_to_csv(source: Path, target: Path) -> None:
    book = load_workbook(source, read_only=True, data_only=True)
    try:
        with target.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            for row in book.active.iter_rows(values_only=True):
                writer.writerow(["" if value is None else value for value in row])
    finally:
        book.close()


def _text_to_pdf(source: Path, target: Path) -> None:
    document = canvas.Canvas(str(target))
    text = document.beginText(48, 800)
    for line in source.read_text(encoding="utf-8-sig").splitlines():
        if text.getY() < 48:
            document.drawText(text)
            document.showPage()
            text = document.beginText(48, 800)
        text.textLine(line[:120])
    document.drawText(text)
    document.save()


def convert(source: Path, target: Path) -> None:
    source, target = Path(source).resolve(strict=True), Path(target).resolve()
    if not source.is_file() or source == target:
        raise ValueError("Choose a file and a different output path.")
    fmt = target.suffix.lower().lstrip(".")
    if fmt not in available_formats(source):
        raise ValueError(f"{source.suffix} to .{fmt} is not supported.")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(f"Output already exists: {target.name}")
    group = kind(source)
    if group == "Image":
        _save_image(source, target, fmt)
    elif group == "PDF" and fmt == "txt":
        text = "\n\n".join(page.extract_text() or "" for page in PdfReader(str(source)).pages)
        target.write_text(text, encoding="utf-8")
    elif group == "PDF":
        _pdf_to_image(source, target, fmt)
    elif group in {"Video", "Audio"}:
        command = [ffmpeg_binary(), "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(source), "-y"]
        if fmt in {"mp4", "mov"}:
            command += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"]
        elif fmt in {"webm"}:
            command += ["-c:v", "libvpx-vp9", "-c:a", "libopus"]
        elif fmt == "gif":
            command += ["-vf", "fps=12,scale=720:-1:flags=lanczos"]
        command.append(str(target))
        _run(command)
    elif source.suffix.lower() == ".csv" and fmt == "xlsx":
        _csv_to_xlsx(source, target)
    elif source.suffix.lower() == ".xlsx" and fmt == "csv":
        _xlsx_to_csv(source, target)
    elif source.suffix.lower() == ".docx" and fmt == "txt":
        document = Document(source)
        target.write_text("\n".join(p.text for p in document.paragraphs), encoding="utf-8")
    elif source.suffix.lower() == ".csv" and fmt == "txt":
        shutil.copyfile(source, target)
    elif source.suffix.lower() == ".txt" and fmt == "pdf":
        _text_to_pdf(source, target)
    else:
        _office(source, target, fmt)


def compress(paths: list[Path], target: Path, progress=None) -> None:
    """Create a lossless ZIP archive, refusing collisions and input replacement."""
    sources = [Path(path).resolve(strict=True) for path in paths]
    target = Path(target).resolve()
    if not sources or any(not path.is_file() for path in sources):
        raise ValueError("Add one or more files before compressing.")
    if len({path.name.casefold() for path in sources}) != len(sources):
        raise ValueError("Files with the same name cannot share one ZIP archive.")
    if target.exists() or target in sources:
        raise FileExistsError(f"Output already exists: {target.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with ZipFile(target, "x", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            for index, path in enumerate(sources):
                archive.write(path, arcname=path.name)
                if progress:
                    progress(index, path.name)
    except Exception:
        target.unlink(missing_ok=True)
        raise


def reduced_extension(source: Path) -> str | None:
    group = kind(source)
    if group == "Image":
        return "webp"
    if group == "PDF":
        return "pdf"
    if group == "Video":
        return "mp4"
    if group == "Audio":
        return "mp3"
    return None


def _media_duration(source: Path) -> float:
    result = subprocess.run([ffmpeg_binary(), "-hide_banner", "-i", str(source)], capture_output=True, text=True, timeout=30, shell=False)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        raise ValueError("Could not read media duration.")
    hours, minutes, seconds = match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    if duration <= 0:
        raise ValueError("Media duration must be greater than zero.")
    return duration


def reduce_size(source: Path, target: Path, target_mb: float) -> None:
    """Try to meet a per-file upload limit without truncating media."""
    source, target = Path(source).resolve(strict=True), Path(target).resolve()
    limit = int(target_mb * 1024 * 1024)
    if limit <= 0 or not source.is_file():
        raise ValueError("Choose a valid file and a target size above 0 MB.")
    if source.stat().st_size <= limit:
        raise ValueError("This file is already below the target size.")
    if target.exists() or source == target:
        raise FileExistsError(f"Output already exists: {target.name}")
    expected = reduced_extension(source)
    if expected is None or target.suffix.lower() != f".{expected}":
        raise ValueError("Target-size compression is supported for images, PDFs, video, and audio.")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        if kind(source) == "Image":
            with _image(source) as opened:
                if getattr(opened, "n_frames", 1) > 1:
                    raise ValueError("Animated images need ZIP compression or a manual conversion.")
                image = ImageOps.exif_transpose(opened).convert("RGBA")
            for scale in (1, 0.85, 0.7, 0.55):
                resized = image if scale == 1 else image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
                for quality in (85, 65, 45, 25):
                    resized.save(target, "WEBP", quality=quality, method=6)
                    if target.stat().st_size <= limit:
                        return
        elif kind(source) == "PDF":
            for scale, quality in ((2, 80), (1.6, 65), (1.3, 50)):
                pdf = pdfium.PdfDocument(str(source))
                document = canvas.Canvas(str(target), pageCompression=1)
                try:
                    for page in pdf:
                        width, height = page.get_size()
                        image = page.render(scale=scale).to_pil().convert("RGB")
                        buffer = io.BytesIO()
                        image.save(buffer, "JPEG", quality=quality, optimize=True)
                        buffer.seek(0)
                        document.setPageSize((width, height))
                        document.drawImage(ImageReader(buffer), 0, 0, width, height)
                        document.showPage()
                    document.save()
                finally:
                    pdf.close()
                if target.stat().st_size <= limit:
                    return
        else:
            duration = _media_duration(source)
            is_video = kind(source) == "Video"
            for factor in (0.9, 0.75, 0.6):
                total_bitrate = max(24_000, int(limit * 8 / duration * factor))
                command = [ffmpeg_binary(), "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(source), "-y"]
                if is_video:
                    audio_bitrate = min(96_000, max(24_000, total_bitrate // 4))
                    command += ["-c:v", "libx264", "-b:v", str(max(20_000, total_bitrate - audio_bitrate)), "-c:a", "aac", "-b:a", str(audio_bitrate), "-pix_fmt", "yuv420p"]
                else:
                    command += ["-vn", "-c:a", "libmp3lame", "-b:a", str(min(320_000, total_bitrate))]
                _run(command + [str(target)])
                if target.stat().st_size <= limit:
                    return
        raise ValueError("Could not reach the target size while keeping the full file. Try a larger limit.")
    except Exception:
        target.unlink(missing_ok=True)
        raise
