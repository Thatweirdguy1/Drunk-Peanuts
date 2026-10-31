"""Synthetic SmartArt fidelity and independent edit/duplicate round trips."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import io,tempfile,unittest
from pathlib import Path
from lxml import etree
from pptx import Presentation
from pptx.opc.package import Part
from pptx.opc.packuri import PackURI
from pptx.oxml import parse_xml
from pptx.util import Inches,Pt
from pptx.enum.shapes import MSO_SHAPE,MSO_SHAPE_TYPE
from pptx.dml.color import RGBColor
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter,QColor
from PySide6.QtCore import QRectF
from dazzle import Dazzle
from office_editing import duplicate_slide
from slide_rendering import A,P,D,R,SlideTheme,diagram_nodes,diagram_part,replace_diagram_node,text_html


def synthetic_deck():
    deck=Presentation();deck.slide_width=Inches(13.333);deck.slide_height=Inches(7.5)
    slide=deck.slides.add_slide(deck.slide_layouts[6]);package=deck.part.package
    banner=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,Pt(30),Pt(420),Pt(900),Pt(70))
    banner.fill.solid();banner.fill.fore_color.rgb=RGBColor.from_string('1B325F')
    slide.shapes._spTree.remove(banner._element);slide.slide_layout.shapes._spTree.insert_element_before(banner._element,'p:extLst')
    drawing=f'''<dsp:drawing xmlns:dsp="{D}" xmlns:a="{A}"><dsp:spTree><dsp:nvGrpSpPr><dsp:cNvPr id="0" name=""/><dsp:cNvGrpSpPr/></dsp:nvGrpSpPr><dsp:grpSpPr/>
    <dsp:sp modelId="presentation-node"><dsp:nvSpPr><dsp:cNvPr id="1" name="Diagram box"/><dsp:cNvSpPr/></dsp:nvSpPr><dsp:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="3810000" cy="1905000"/></a:xfrm><a:prstGeom prst="rect"/><a:solidFill><a:schemeClr val="accent1"/></a:solidFill><a:ln><a:noFill/></a:ln></dsp:spPr><dsp:style><a:fontRef idx="minor"><a:schemeClr val="lt1"/></a:fontRef></dsp:style><dsp:txBody><a:bodyPr anchor="ctr"/><a:lstStyle/><a:p><a:pPr algn="ctr"/><a:r><a:rPr sz="2400"/><a:t>Start here</a:t></a:r></a:p></dsp:txBody></dsp:sp></dsp:spTree></dsp:drawing>'''
    draw=Part(PackURI('/ppt/diagrams/drawing1.xml'),'application/vnd.ms-office.drawingml.diagramDrawing+xml',package,drawing.encode())
    drawing_id=slide.part.relate_to(draw,'http://schemas.microsoft.com/office/2007/relationships/diagramDrawing')
    data=f'''<dgm:dataModel xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram" xmlns:a="{A}" xmlns:dsp="{D}"><dgm:ptLst><dgm:pt modelId="data-node"><dgm:prSet/><dgm:t><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>Start here</a:t></a:r></a:p></dgm:t></dgm:pt><dgm:pt modelId="presentation-node" type="pres"><dgm:prSet presAssocID="data-node"/></dgm:pt></dgm:ptLst><dgm:extLst><dgm:ext uri="cache"><dsp:dataModelExt relId="{drawing_id}"/></dgm:ext></dgm:extLst></dgm:dataModel>'''
    part=Part(PackURI('/ppt/diagrams/data1.xml'),'application/vnd.openxmlformats-officedocument.drawingml.diagramData+xml',package,data.encode())
    rid=slide.part.relate_to(part,'http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData')
    shape=parse_xml(f'''<p:graphicFrame xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}" xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram"><p:nvGraphicFramePr><p:cNvPr id="2" name="Process diagram"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr><p:xfrm><a:off x="381000" y="381000"/><a:ext cx="3810000" cy="1905000"/></p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/diagram"><dgm:relIds r:dm="{rid}"/></a:graphicData></a:graphic></p:graphicFrame>''')
    slide.shapes._spTree.insert_element_before(shape,'p:extLst')
    title=slide.shapes.add_textbox(Pt(45),Pt(425),Pt(850),Pt(60));title.text='A visible process';title.text_frame.paragraphs[0].font.size=Pt(30);title.text_frame.paragraphs[0].font.color.rgb=RGBColor(255,255,255)
    return deck


class PresentationFidelityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_rich_text_accept_and_cancel_preserve_native_runs(self):
        from unittest.mock import patch
        from PySide6.QtWidgets import QDialog,QTextEdit
        from presentation_tools import rich_text
        editor=Dazzle();editor.insert_text('Original text')
        before=editor._bytes()
        with patch.object(QDialog,'exec',return_value=QDialog.Rejected):rich_text(editor)
        self.assertEqual(editor._bytes(),before)
        def accept(dialog):
            text=dialog.findChild(QTextEdit)
            text.setHtml('<p align="center"><span style="font-size:20pt;color:#202b3d"><b>Bold</b> and plain</span></p>')
            return QDialog.Accepted
        with patch.object(QDialog,'exec',accept):rich_text(editor)
        shape=editor.deck.slides[0].shapes[-1];runs=shape.text_frame.paragraphs[0].runs
        self.assertEqual(shape.text,'Bold and plain');self.assertTrue(runs[0].font.bold)
        self.assertEqual(runs[0].font.size.pt,20)
        editor.undo();self.assertEqual(editor.deck.slides[0].shapes[-1].text,'Original text')
        editor.dirty=False;editor.close()
    def test_general_editing_workflow_and_roundtrip(self):
        from presentation_tools import (choose_many,selected,group_objects,ungroup_objects,
            copy_objects,paste_objects,arrange_objects,distribute_objects,flip_objects,
            paragraph_format,crop_image,hide_slide,slide_layout,set_hyperlink,insert_connector)
        from pptx.enum.text import PP_ALIGN
        from dazzle import SlideShow
        editor=Dazzle();first=editor.insert_text('First');second=editor.insert_text('Second');third=editor.insert_shape()
        first.left=Pt(100);second.left=Pt(400);third.left=Pt(700)
        choose_many(editor,[first,second,third]);distribute_objects(editor)
        shapes=selected(editor);self.assertEqual(len(shapes),3)
        arrange_objects(editor,'Top');self.assertEqual(len({s.top for s in selected(editor)}),1)
        group_objects(editor);self.assertEqual(selected(editor)[0].shape_type,MSO_SHAPE_TYPE.GROUP)
        ungroup_objects(editor);self.assertEqual(len(selected(editor)),3)
        flip_objects(editor);self.assertEqual(selected(editor)[0]._element.xfrm.get('flipH'),'1')
        copy_objects(editor);count=len(editor.deck.slides[0].shapes);editor.add();paste_objects(editor)
        self.assertEqual(len(selected(editor)),3);self.assertEqual(len(editor.deck.slides[0].shapes),count)
        choose_many(editor,[s for s in editor.deck.slides[1].shapes if s.has_text_frame][-2:]);paragraph_format(editor,PP_ALIGN.CENTER,'numbers')
        self.assertTrue(all(s.text_frame.paragraphs[0].alignment==PP_ALIGN.CENTER for s in selected(editor)))
        shape=selected(editor)[0];choose_many(editor,[shape]);set_hyperlink(editor,'https://example.com')
        self.assertEqual(editor.selected_shape().click_action.hyperlink.address,'https://example.com')
        with self.assertRaises(ValueError):set_hyperlink(editor,'file:///private.txt')
        choose_many(editor,[s for s in editor.deck.slides[1].shapes if s.has_text_frame][-2:]);insert_connector(editor)
        connector=selected(editor)[0];self.assertIsNotNone(connector._element.find('.//{'+A+'}tailEnd'))
        editor.undo();self.assertNotEqual(editor.deck.slides[1].shapes[-1].shape_type,MSO_SHAPE_TYPE.LINE)
        editor.redo();slide_layout(editor,6);hide_slide(editor)
        self.assertEqual(editor.deck.slides[1]._element.get('show'),'0')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'picture.png';image=QImage(30,20,QImage.Format_RGB32);image.fill(QColor('red'));image.save(str(path))
            picture=editor.insert_image(path);crop_image(editor,[.1,.2,.1,.2]);self.assertAlmostEqual(picture.crop_left,.1)
            with self.assertRaises(ValueError):crop_image(editor,[.8,0,.8,0])
            target=Path(folder)/'edited.pptx';editor._write(target);deck=Presentation(target)
            self.assertEqual(len(deck.slides),2);self.assertEqual(deck.slides[1]._element.get('show'),'0')
        editor.dirty=False;editor.close()
    def test_diagram_theme_master_readonly_and_independent_roundtrip(self):
        editor=Dazzle();editor.deck=synthetic_deck();editor.index=0;editor.refresh()
        before={str(p.partname):p.blob for p in editor.deck.part.package.iter_parts()}
        scene=editor.make_scene(0,False);im=QImage(960,540,QImage.Format_ARGB32);im.fill(0);p=QPainter(im);scene.render(p,QRectF(0,0,960,540));p.end()
        self.assertEqual(im.pixelColor(40,440).name(),'#1b325f')
        self.assertNotEqual(im.pixelColor(50,50).name(),'#ffffff')
        self.assertEqual(before,{str(p.partname):p.blob for p in editor.deck.part.package.iter_parts()})
        shape=editor.deck.slides[0].shapes[0];self.assertEqual(len(diagram_nodes(shape)[4]),1)
        editor.choose(shape);editor.duplicate_object();copy_shape=editor.deck.slides[0].shapes[-1]
        self.assertIsNot(diagram_part(copy_shape),diagram_part(shape))
        editor.change(lambda:replace_diagram_node(copy_shape,0,'Independent copy'))
        self.assertIn(b'Start here',diagram_part(shape).blob);self.assertIn(b'Independent copy',diagram_part(copy_shape).blob)
        editor.undo();self.assertNotIn(b'Independent copy',diagram_part(editor.deck.slides[0].shapes[-1]).blob)
        editor.redo();duplicate_slide(editor)
        self.assertEqual(editor.deck.slides[0].slide_layout,editor.deck.slides[1].slide_layout)
        duplicated=editor.deck.slides[1].shapes[0];replace_diagram_node(duplicated,0,'New slide')
        self.assertIn(b'Start here',diagram_part(editor.deck.slides[0].shapes[0]).blob)
        self.assertIn(b'New slide',diagram_part(duplicated).blob)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'process.pptx';editor._write(path);deck=Presentation(path)
            self.assertIn(b'New slide',diagram_part(deck.slides[1].shapes[0]).blob)
        editor.dirty=False;editor.close()

if __name__=='__main__':unittest.main()
