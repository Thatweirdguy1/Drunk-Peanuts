"""Local slide comments, native alternative text and document checks."""
from datetime import datetime,timezone
from lxml import etree
from pptx.opc.constants import RELATIONSHIP_TYPE as RT,CONTENT_TYPE as CT
from pptx.opc.package import XmlPart
from pptx.oxml.xmlchemy import OxmlElement
from PySide6.QtWidgets import (QDialog,QFormLayout,QLineEdit,QPlainTextEdit,QDialogButtonBox,QVBoxLayout,
    QListWidget,QPushButton,QHBoxLayout,QLabel)
from slide_rendering import P
from slide_design import save_xml


def nonvisual(shape):
    return shape._element.find('.//{'+P+'}cNvPr')


def alt_text(shape,title,description):
    if len(title)>500 or len(description)>20000:raise ValueError('Alternative text is too long.')
    node=nonvisual(shape)
    if node is None:raise ValueError('This object has no editable alternative text.')
    node.set('title',title.strip());node.set('descr',description.strip())


def alt_dialog(editor):
    shape=editor.selected_shape()
    if shape is None:raise ValueError('Select an object first.')
    node=nonvisual(shape);dialog=QDialog(editor);dialog.setWindowTitle('Alternative text');form=QFormLayout(dialog)
    title=QLineEdit(node.get('title',''));description=QPlainTextEdit(node.get('descr',''));title.setAccessibleName('Alternative title');description.setAccessibleName('Alternative description');form.addRow('Title',title);form.addRow('Description',description)
    buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
    if dialog.exec()==QDialog.Accepted:editor.change(lambda:alt_text(shape,title.text(),description.toPlainText()))


def related(part,kind):return next((rel.target_part for rel in part.rels.values() if rel.reltype==kind and not rel.is_external),None)


def add_comment(deck,slide,text,author='Local author'):
    text=text.strip();author=author.strip()
    if not text or len(text)>10000 or not author or len(author)>120:raise ValueError('Enter a comment of 1–10,000 characters and an author name of 1–120 characters.')
    package=deck.part.package;authors=related(deck.part,RT.COMMENT_AUTHORS)
    if authors is None:
        root=OxmlElement('p:cmAuthorLst');authors=XmlPart(package.next_partname('/ppt/commentAuthors%d.xml'),CT.PML_COMMENT_AUTHORS,package,root);deck.part.relate_to(authors,RT.COMMENT_AUTHORS)
    root=etree.fromstring(authors.blob);entry=next((n for n in root if n.get('name')==author),None)
    if entry is None:
        identifier=max((int(n.get('id','0')) for n in root),default=-1)+1;entry=OxmlElement('p:cmAuthor');entry.set('id',str(identifier));entry.set('name',author);entry.set('initials',''.join(word[0] for word in author.split())[:4]);entry.set('lastIdx','0');entry.set('clrIdx',str(identifier%8));root.append(entry)
    index=int(entry.get('lastIdx','0'))+1;entry.set('lastIdx',str(index));save_xml(authors,root)
    part=related(slide.part,RT.COMMENTS)
    if part is None:
        part=XmlPart(package.next_partname('/ppt/comments/comment%d.xml'),CT.PML_COMMENTS,package,OxmlElement('p:cmLst'));slide.part.relate_to(part,RT.COMMENTS)
    root=etree.fromstring(part.blob);comment=OxmlElement('p:cm');comment.set('authorId',entry.get('id'));comment.set('idx',str(index));comment.set('dt',datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
    position=OxmlElement('p:pos');position.set('x','0');position.set('y','0');comment.append(position);body=OxmlElement('p:text');body.text=text;comment.append(body);root.append(comment);save_xml(part,root)


def comments(deck,slide):
    authors=related(deck.part,RT.COMMENT_AUTHORS);part=related(slide.part,RT.COMMENTS)
    names={n.get('id'):n.get('name','Local author') for n in etree.fromstring(authors.blob)} if authors else {}
    if part is None:return []
    return [(names.get(n.get('authorId'),'Unknown author'),n.findtext('{'+P+'}text',''),n.get('idx')) for n in etree.fromstring(part.blob)]


def comments_dialog(editor):
    dialog=QDialog(editor);dialog.setWindowTitle('Local slide comments');dialog.resize(680,520);layout=QVBoxLayout(dialog);listing=QListWidget();listing.setWordWrap(True);layout.addWidget(listing)
    layout.addWidget(QLabel('Legacy PPTX slide comments. Existing threaded comments are preserved but are not edited here.'))
    author=QLineEdit('Local author');author.setAccessibleName('Comment author');layout.addWidget(author);body=QPlainTextEdit();body.setAccessibleName('New comment');body.setPlaceholderText('Add a local review note…');layout.addWidget(body)
    def refresh():listing.clear();listing.addItems([f'{name}: {text}' for name,text,_ in comments(editor.deck,editor.deck.slides[editor.index])])
    def add():
        def apply():
            editor.change(lambda:add_comment(editor.deck,editor.deck.slides[editor.index],body.toPlainText(),author.text()));body.clear();refresh()
        editor.report(apply)
    def remove():
        row=listing.currentRow()
        if row<0:return
        def apply():
            part=related(editor.deck.slides[editor.index].part,RT.COMMENTS);root=etree.fromstring(part.blob);root.remove(root[row]);save_xml(part,root)
        editor.change(apply);refresh()
    row=QHBoxLayout();layout.addLayout(row)
    for text,callback in [('Add comment',add),('Remove selected',remove),('Close',dialog.accept)]:button=QPushButton(text);button.clicked.connect(callback);row.addWidget(button)
    refresh();dialog.exec()


def accessibility_issues(deck):
    issues=[]
    for index,slide in enumerate(deck.slides):
        title=slide.shapes.title
        if title is None or not title.text.strip():issues.append((index,0,'Add a descriptive slide title.'))
        for shape in slide.shapes:
            node=nonvisual(shape)
            if (shape.shape_type in (13,16) or shape.has_chart) and (node is None or not node.get('descr','').strip()):issues.append((index,shape.shape_id,f'{shape.name}: add alternative text.'))
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    fonts=[run.font for run in paragraph.runs] or [paragraph.font]
                    if any(font.size is not None and font.size.pt<14 for font in fonts):issues.append((index,shape.shape_id,f'{shape.name}: text below 14 pt may be hard to read.'));break
            if shape.has_table and not shape.table.first_row:issues.append((index,shape.shape_id,f'{shape.name}: mark the first row as a table header.'))
    return issues


def accessibility_dialog(editor):
    dialog=QDialog(editor);dialog.setWindowTitle('Accessibility checks');dialog.resize(740,500);layout=QVBoxLayout(dialog);layout.addWidget(QLabel('Checks slide titles, image/chart descriptions, small text and table headers. Review reading order and contrast separately.'))
    listing=QListWidget();listing.setWordWrap(True);layout.addWidget(listing);issues=accessibility_issues(editor.deck);listing.addItems([f'Slide {index+1} · {message}' for index,_,message in issues] or ['No issues found by these checks.'])
    def locate():
        row=listing.currentRow()
        if not 0<=row<len(issues):return
        index,sid,_=issues[row];editor.select(index)
        shape=next((s for s in editor.deck.slides[index].shapes if s.shape_id==sid),None)
        if shape is not None:editor.choose(shape)
    button=QPushButton('Locate selected issue');button.clicked.connect(locate);layout.addWidget(button);close=QPushButton('Close');close.clicked.connect(dialog.accept);layout.addWidget(close);dialog.exec()


def reading_order_dialog(editor):
    dialog=QDialog(editor);dialog.setWindowTitle('Reading order and stacking');dialog.resize(620,500);layout=QVBoxLayout(dialog);layout.addWidget(QLabel('First to last follows native object order. Reordering also changes back-to-front stacking.'))
    shapes=list(editor.deck.slides[editor.index].shapes);listing=QListWidget();listing.addItems([s.name+(' · '+s.text[:60] if s.has_text_frame else '') for s in shapes]);listing.setDragDropMode(QListWidget.InternalMove)
    from PySide6.QtCore import Qt
    for i,shape in enumerate(shapes):listing.item(i).setData(Qt.UserRole,shape.shape_id)
    layout.addWidget(listing);row=QHBoxLayout();layout.addLayout(row)
    def move(delta):
        index=listing.currentRow();target=index+delta
        if 0<=index<listing.count() and 0<=target<listing.count():listing.insertItem(target,listing.takeItem(index));listing.setCurrentRow(target)
    for label,delta in [('Move earlier',-1),('Move later',1)]:button=QPushButton(label);button.clicked.connect(lambda checked=False,step=delta:move(step));row.addWidget(button)
    buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);layout.addWidget(buttons);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
    if dialog.exec()==QDialog.Accepted:
        order=[listing.item(i).data(Qt.UserRole) for i in range(listing.count())]
        def apply():
            tree=editor.deck.slides[editor.index].shapes._spTree;nodes={s.shape_id:s._element for s in shapes}
            for sid in order:tree.remove(nodes[sid])
            for i,sid in enumerate(order):tree.insert(i+2,nodes[sid])
        editor.change(apply)
