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
        with self.assertRaises(ValueError):structural_edit(table,'row',0,False)
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
