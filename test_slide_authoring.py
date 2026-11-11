"""Native design, geometry, and on-canvas text regression checks."""
import os,io,math,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QRectF,Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication,QDialog,QTableWidget
from unittest.mock import patch
from lxml import etree
from pptx import Presentation
from dazzle import Dazzle
from preset_geometry import presets,paths
from slide_design import apply_theme,clone_layout,add_placeholder,master_dialog
from slide_rendering import SlideTheme
from slide_text import InlineText


class AuthoringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_table_structure_merges_roundtrip_and_cancel(self):
        from slide_tables import structural_edit,table_dialog
        editor=Dazzle();shape=editor.insert_table(2,2);table=shape.table
        table.cell(0,0).text='Preserved';table.cell(1,1).text='Last cell'
        structural_edit(table,'row',1,True);self.assertEqual(len(table.rows),3)
        self.assertEqual(table.cell(1,0).text,'');self.assertEqual(table.cell(2,1).text,'Last cell')
        structural_edit(table,'column',2,True);self.assertEqual(len(table.columns),3);self.assertEqual(table.cell(0,2).text,'')
        structural_edit(table,'row',1,False);structural_edit(table,'column',2,False)
        table.cell(0,0).merge(table.cell(0,1))
        structural_edit(table,'row',1,True);structural_edit(table,'row',1,False)
        self.assertTrue(table.cell(0,0).is_merge_origin)
        table.cell(0,0).split();structural_edit(table,'row',1,False)
        with self.assertRaises(ValueError):structural_edit(table,'row',0,False)
        before=shape._element.xml
        with patch.object(QDialog,'exec',return_value=QDialog.Rejected):table_dialog(editor,shape)
        self.assertEqual(shape._element.xml,before)
        def save_dialog(dialog):
            dialog.findChild(QTableWidget).item(0,0).setText('Edited grid cell')
            return QDialog.Accepted
        with patch.object(QDialog,'exec',save_dialog):table_dialog(editor,shape)
        self.assertEqual(editor.deck.slides[0].shapes[-1].table.cell(0,0).text,'Edited grid cell')
        editor.undo()
        saved=Presentation(io.BytesIO(editor._bytes())).slides[0].shapes[-1].table
        self.assertEqual(len(saved.rows),1);self.assertIn('Preserved',saved.cell(0,0).text)
        editor.dirty=False;editor.close()
    def test_structure_changes_keep_merged_content_and_spans(self):
        from slide_tables import structural_edit
        editor=Dazzle();shape=editor.insert_table(4,4);table=shape.table
        table.cell(0,0).text='Merged heading';table.cell(0,0).merge(table.cell(2,2))
        structural_edit(table,'row',1,True);structural_edit(table,'column',1,True)
        self.assertEqual((table.cell(0,0).span_height,table.cell(0,0).span_width),(4,4))
        structural_edit(table,'row',0,False);structural_edit(table,'column',0,False)
        self.assertEqual((table.cell(0,0).span_height,table.cell(0,0).span_width),(3,3))
        self.assertEqual(table.cell(0,0).text,'Merged heading')
        loaded=Presentation(io.BytesIO(editor._bytes())).slides[0].shapes[-1].table
        self.assertEqual(loaded.cell(0,0).text,'Merged heading');self.assertEqual(loaded.cell(0,0).span_height,3)
        editor.dirty=False;editor.close()
    def test_freeform_boolean_geometry_and_undo(self):
        from slide_shapes import insert_path,combine,set_path
        from presentation_tools import choose_many
        from PySide6.QtGui import QPainterPath
        from preset_geometry import paths
        editor=Dazzle();baseline=len(editor.deck.slides[0].shapes);first=QPainterPath();first.addRect(QRectF(10,10,100,100));second=QPainterPath();second.addRect(QRectF(60,10,100,100))
        a=editor.change(lambda:insert_path(editor,first));b=editor.change(lambda:insert_path(editor,second))
        a.text='First label';b.text='Second label';sid=a.shape_id
        choose_many(editor,[a,b]);combined=combine(editor,'Union');self.assertAlmostEqual(combined.width/12700,150)
        self.assertEqual(combined.shape_id,sid);self.assertIn('First label',combined.text);self.assertIn('Second label',combined.text)
        self.assertEqual(len(editor.deck.slides[0].shapes),baseline+1);editor.undo();self.assertEqual(len(editor.deck.slides[0].shapes),baseline+2)
        choose_many(editor,list(editor.deck.slides[0].shapes)[-2:]);combined=combine(editor,'Subtract');self.assertAlmostEqual(combined.width/12700,50)
        curve=QPainterPath();curve.moveTo(10,10);curve.cubicTo(20,5,40,5,50,10);curve.lineTo(10,10);set_path(combined,curve)
        loaded=Presentation(io.BytesIO(editor._bytes())).slides[0].shapes[-1]
        self.assertTrue(loaded._element.spPr.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}cubicBezTo'))
        self.assertTrue(paths(loaded._element.spPr,QRectF(0,0,loaded.width/12700,loaded.height/12700)))
        editor.dirty=False;editor.close()
    def test_native_comments_alt_text_and_checks_roundtrip(self):
        from slide_review import add_comment,comments,alt_text,nonvisual,accessibility_issues,reading_order_dialog
        editor=Dazzle();shape=editor.insert_shape();alt_text(shape,'Process','Three steps from idea to presentation.')
        editor.change(lambda:add_comment(editor.deck,editor.deck.slides[0],'Clarify this step.','Reviewer'))
        editor.change(lambda:add_comment(editor.deck,editor.deck.slides[0],'Use a shorter heading.','Reviewer'))
        loaded=Presentation(io.BytesIO(editor._bytes()));notes=comments(loaded,loaded.slides[0])
        self.assertEqual([row[1] for row in notes],['Clarify this step.','Use a shorter heading.']);self.assertEqual([row[2] for row in notes],['1','2'])
        self.assertEqual(nonvisual(loaded.slides[0].shapes[-1]).get('descr'),'Three steps from idea to presentation.')
        self.assertTrue(any('title' in message for _,_,message in accessibility_issues(loaded)))
        before=editor._bytes()
        with patch.object(QDialog,'exec',return_value=QDialog.Rejected):reading_order_dialog(editor)
        self.assertEqual(editor._bytes(),before)
        editor.undo();self.assertEqual(len(comments(editor.deck,editor.deck.slides[0])),1)
        editor.dirty=False;editor.close()
    def test_template_slideshow_packages_and_import_safety(self):
        import tempfile
        from pathlib import Path
        from slide_formats import NATIVE,load
        from zipfile import ZipFile
        editor=Dazzle();editor.insert_text('Reusable template content')
        with tempfile.TemporaryDirectory() as folder:
            for suffix,kind in NATIVE.items():
                target=Path(folder)/('Source'+suffix);editor._write(target)
                with ZipFile(target) as archive:self.assertIn(kind.encode(),archive.read('[Content_Types].xml'))
                self.assertIn('Reusable template content',' '.join(s.text for s in load(target).slides[0].shapes if s.has_text_frame))
                opened=Dazzle();opened.open(target);self.assertIsNone(opened.path)
                with self.assertRaises(ValueError):opened._write(target)
                opened.dirty=False;opened.close()
        editor.dirty=False;editor.close()
    def test_notes_and_handout_pdf_layouts(self):
        from slide_printing import export_pdf
        import tempfile
        from pathlib import Path
        from pypdf import PdfReader
        from PySide6.QtGui import QFontDatabase
        if not QFontDatabase.families():
            font=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/arial.ttf'
            if font.is_file():QFontDatabase.addApplicationFont(str(font))
        editor=Dazzle();editor.set_notes('Keep this explanation clear.');editor.add();editor.set_notes('Second slide notes.')
        with tempfile.TemporaryDirectory() as folder:
            notes=Path(folder)/'Notes.pdf';self.assertEqual(export_pdf(editor,notes,'Notes'),2)
            if QFontDatabase.families():self.assertIn('Keep this explanation clear.',' '.join(' '.join(p.extract_text() for p in PdfReader(notes).pages).split()))
            handout=Path(folder)/'Handout.pdf';self.assertEqual(export_pdf(editor,handout,'Handouts',2),1)
            self.assertEqual(len(PdfReader(handout).pages),1)
        editor.dirty=False;editor.close()
    def test_chart_types_options_combination_and_type_change(self):
        from dazzle import CHARTS,chart_info
        from slide_charts import apply_options,options,change_type
        from office_insert import chart_png
        from PySide6.QtGui import QImage
        editor=Dazzle();data={'categories':['Q1','Q2','Q3'],'series':[{'name':'Revenue','values':[10,15,20]},{'name':'Costs','values':[5,8,9]}]}
        for kind in CHARTS:
            values=data if kind not in ('Pie','Doughnut') else dict(categories=data['categories'],series=data['series'][:1])
            if kind=='Scatter':values=dict(categories=[1,2,3],series=data['series'])
            shape=editor.insert_chart(kind,values);self.assertEqual(chart_info(shape)[0],kind)
            self.assertFalse(QImage.fromData(chart_png(values,kind,options=options(shape.chart))).isNull(),kind)
        settings=dict(title='Quarterly review',legend=True,labels=True,x_title='Quarter',y_title='Revenue',minimum=0,maximum=30)
        apply_options(shape.chart,settings);self.assertEqual(options(shape.chart)['title'],'Quarterly review')
        sid=shape.shape_id;changed=change_type(editor,shape,'Line',data);self.assertEqual(changed.shape_id,sid)
        self.assertEqual(options(changed.chart)['maximum'],30);self.assertEqual(options(changed.chart)['title'],'Quarterly review')
        saved=Presentation(io.BytesIO(editor._bytes()));self.assertEqual(chart_info(saved.slides[0].shapes[-1])[0],'Line')
        editor.undo();self.assertEqual(chart_info(editor.deck.slides[0].shapes[-1])[0],'Column + line')
        before={str(part.partname):part.blob for part in editor.deck.part.package.iter_parts()};editor.thumbnail(0)
        self.assertEqual(before,{str(part.partname):part.blob for part in editor.deck.part.package.iter_parts()})
        editor.dirty=False;editor.close()
    def test_all_presets_and_on_canvas_text_commit_cancel(self):
        for name in presets():
            node=etree.fromstring(('<a:spPr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:prstGeom prst="'+name+'"/></a:spPr>').encode())
            resolved=paths(node,QRectF(0,0,300,200));self.assertTrue(resolved,name)
            for path,_,_ in resolved:self.assertTrue(math.isfinite(path.boundingRect().width()),name)
        editor=Dazzle();shape=editor.insert_text('Original');editor.choose(shape);item=editor.scene.selectedItems()[0]
        inline=InlineText(item);cursor=inline.textCursor();cursor.select(QTextCursor.Document);cursor.insertText('Edited directly');inline.finish()
        self.assertEqual(editor.deck.slides[0].shapes[-1].text,'Edited directly');editor.undo()
        item=next(item for item in editor.scene.items() if item.interactive and item.native_shape.shape_id==shape.shape_id)
        inline=InlineText(item);cursor=inline.textCursor();cursor.select(QTextCursor.Document);cursor.insertText('Cancelled');inline.finish(True)
        self.assertEqual(editor.deck.slides[0].shapes[-1].text,'Original');editor.dirty=False;editor.close()
    def test_master_layout_theme_roundtrip_and_cancel(self):
        editor=Dazzle();before={str(p.partname):p.blob for p in editor.deck.part.package.iter_parts()}
        with patch.object(QDialog,'exec',return_value=QDialog.Rejected):master_dialog(editor)
        self.assertEqual(before,{str(p.partname):p.blob for p in editor.deck.part.package.iter_parts()})
        theme=SlideTheme(editor.deck.slides[0]);colors={key:'#'+value for key,value in theme.colors.items()};colors['accent1']='#9457ff'
        editor.change(lambda:apply_theme(editor.deck,colors,'Arial','Georgia'))
        self.assertEqual(SlideTheme(editor.deck.slides[0]).fonts['minor'],'Georgia')
        layout=clone_layout(editor.deck,editor.deck.slide_layouts[1],'Production notes');placeholder=add_placeholder(layout,'body')
        saved=Presentation(io.BytesIO(editor._bytes()));self.assertEqual(saved.slide_layouts[-1].name,'Production notes')
        self.assertEqual(saved.slide_layouts[-1].shapes[-1].placeholder_format.idx,placeholder.placeholder_format.idx)
        self.assertEqual(SlideTheme(saved.slides[0]).colors['accent1'].lower(),'9457ff')
        editor.dirty=False;editor.close()

if __name__=='__main__':unittest.main()
