"""Bundled editable starters, copied before use so originals stay intact."""
from pathlib import Path
import shutil

ASSETS = Path(__file__).resolve().parent / 'assets'
TEMPLATES = {
    'Pages': ('Report.docx', 'Letter.docx', 'Meeting notes.docx'),
    'Tables': ('Budget.xlsx', 'Task tracker.xlsx'),
    'Dazzle': ('Presentation.pptx', 'Project update.pptx'),
    'Sketch': ('Blank canvas.png',),
    'Organize': ('Contacts.sqlite',),
    'Formulaic': ('Equations.formulaic',),
    "Writer's Drafts": ('Screenplay.fountain',),
}


def create_document(workspace, name, destination):
    if name not in TEMPLATES.get(workspace, ()):
        raise ValueError('Choose a bundled template')
    destination = Path(destination)
    source = ASSETS / 'templates' / name
    if destination.suffix.lower() != source.suffix.lower():
        raise ValueError(f'This template needs a {source.suffix} filename')
    with source.open('rb') as original, destination.open('xb') as copy:
        shutil.copyfileobj(original, copy)
    return destination
