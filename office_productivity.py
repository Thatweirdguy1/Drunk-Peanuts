"""Pages outline, body statistics and native DOCX core properties."""
import re
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (QDockWidget,QWidget,QVBoxLayout,QLineEdit,QListWidget,
    QListWidgetItem,QDialog,QFormLayout,QDialogButtonBox,QLabel,QMessageBox)
from office_editing import command

FIELDS={'title':'Title','subject':'Subject','author':'Author','keywords':'Keywords','comments':'Description','category':'Category'}


def set_properties(pages,values):
    if not isinstance(values,dict) or any(key not in FIELDS or not isinstance(value,str) or len(value)>255 for key,value in values.items()):
        raise ValueError('Document properties must be supported text fields of at most 255 characters.')
    pages.document_properties.update(values);pages.pending_properties.update(values)
    pages.rich_changed=True;pages.editor.document().setModified(True)


def load_properties(pages,document=None):
    pages.document_properties={key:getattr(document.core_properties,key) or '' if document is not None else '' for key in FIELDS}
    pages.pending_properties={}


def edit_properties(pages):
    dialog=QDialog(pages);dialog.setWindowTitle('Document properties');layout=QFormLayout(dialog);inputs={}
    layout.addRow(QLabel('Saved in DOCX document properties. Does not change body text.\nThese fields are visible to people receiving the file.'))
    for key,label in FIELDS.items():
        field=QLineEdit(pages.document_properties.get(key,''));field.setMaxLength(255);field.setAccessibleName('Document '+label.lower());inputs[key]=field;layout.addRow(label,field)
    buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addRow(buttons)
    if dialog.exec()==QDialog.Accepted:
        changed={key:field.text() for key,field in inputs.items() if field.text()!=pages.document_properties.get(key,'')}
        if changed:set_properties(pages,changed)


def statistics(text):
    text=text.replace('\ufffc','')
    return dict(words=len(re.findall(r"\w+(?:['’\-]\w+)*",text)),characters=len(text),
                characters_without_spaces=sum(not c.isspace() for c in text),
                nonempty_paragraphs=sum(bool(p.strip()) for p in re.split('[\n\u2029]',text)))


def show_statistics(pages):
    result=statistics(pages.editor.toPlainText());text='Document body\n'+'\n'.join(f'{key.replace("_"," ").capitalize()}: {value}' for key,value in result.items())
    selected=pages.editor.textCursor().selectedText()
    if selected:text+='\n\nSelection\n'+'\n'.join(f'{key.replace("_"," ").capitalize()}: {value}' for key,value in statistics(selected).items())
    QMessageBox.information(pages,'Document statistics',text+'\n\nLocal text counts exclude header/footer text and embedded images.\nWord boundaries may differ from Microsoft Word. Physical pages are counted on export.')


def update_outline(pages):
    query=pages.outline_search.text().casefold();pages.outline_list.clear()
    block=pages.editor.document().begin()
    while block.isValid():
        level=block.blockFormat().headingLevel();title=block.text().strip()
        if level and title and query in title.casefold():
            item=QListWidgetItem('  '*(min(level,6)-1)+title);item.setToolTip(f'Heading {level}: {title}')
            item.setData(Qt.UserRole,QTextCursor(block));pages.outline_list.addItem(item)
        block=block.next()
    pages.outline_list.setAccessibleDescription(f'{pages.outline_list.count()} matching headings. Apply Heading styles from Home to add sections.')


def setup_productivity(pages):
    load_properties(pages)
    dock=QDockWidget('Document outline',pages);dock.setObjectName('documentOutline');panel=QWidget();layout=QVBoxLayout(panel)
    pages.outline_search=QLineEdit();pages.outline_search.setPlaceholderText('Filter headings…');pages.outline_search.setAccessibleName('Filter document headings');layout.addWidget(pages.outline_search)
    pages.outline_list=QListWidget();pages.outline_list.setAccessibleName('Document headings');layout.addWidget(pages.outline_list)
    hint=QLabel('Use Home → Heading 1–3 to add sections.\nClick a heading or press Enter to jump.');hint.setWordWrap(True);layout.addWidget(hint)
    dock.setWidget(panel);pages.addDockWidget(Qt.LeftDockWidgetArea,dock);dock.hide();pages.outline_dock=dock
    def jump(item):
        cursor=item.data(Qt.UserRole)
        if isinstance(cursor,QTextCursor):pages.editor.setTextCursor(cursor);pages.editor.ensureCursorVisible();pages.editor.setFocus()
    pages.outline_list.itemClicked.connect(jump);pages.outline_list.itemActivated.connect(jump)
    timer=QTimer(pages);timer.setSingleShot(True);timer.setInterval(200);timer.timeout.connect(lambda:update_outline(pages));pages.outline_timer=timer
    pages.editor.document().contentsChanged.connect(lambda:timer.start() if dock.isVisible() else None)
    pages.outline_search.textChanged.connect(lambda:update_outline(pages))
    def toggle():
        dock.setVisible(not dock.isVisible())
        if dock.isVisible():update_outline(pages);pages.outline_search.setFocus()
    command(pages,'View','Document outline',toggle,'title','Ctrl+Alt+O')
    command(pages,'Review','Document statistics',lambda:show_statistics(pages),'calculate')
    command(pages,'File','Document properties',lambda:edit_properties(pages),'settings')
