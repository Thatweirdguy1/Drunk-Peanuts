"""Animation timing must drive visible scene properties and survive PPTX save."""
import os,io,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from pptx import Presentation
from dazzle import Dazzle,SlideShow
from slide_animation import Effect,write_timeline,timeline,own_effects,motion_path


class AnimationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_native_roundtrip_visible_playback_and_sequencing(self):
        editor=Dazzle();a=editor.insert_text('A visible entrance');b=editor.insert_shape();sid=a.shape_id
        entries=[Effect(sid,'Fade',duration=1),Effect(sid,'Spin','Emphasis','After previous',duration=1),Effect(b.shape_id,'Fly',start='With previous'),Effect(sid,'Fade','Exit',duration=1)]
        editor.change(lambda:write_timeline(editor.deck.slides[0],entries))
        self.assertEqual(len(timeline(editor.deck.slides[0])),4)
        self.assertEqual(len(own_effects(Presentation(io.BytesIO(editor._bytes())).slides[0])),4)
        show=SlideShow(editor,0);player=show.timeline_player;item=player.items[sid]
        self.assertEqual(item.opacity(),0);self.assertEqual(len(player.pending),2)
        player.advance();group=player.running[-1];group.pause();group.setCurrentTime(500)
        self.assertAlmostEqual(item.opacity(),.5,places=1)
        group.setCurrentTime(group.totalDuration());self.assertAlmostEqual(item.rotation(),360)
        player.advance();player.running[-1].pause();player.running[-1].setCurrentTime(1000)
        self.assertEqual(item.opacity(),0)
        show.close();editor.dirty=False;editor.close()

    def test_all_effects_triggers_import_and_readonly_preview(self):
        editor=Dazzle();shape=editor.insert_shape();sid=shape.shape_id
        for effect in ('Appear','Fly','Wipe','Zoom','Pulse','Spin','Motion path'):
            entry=Effect(sid,effect,phase='Emphasis' if effect in ('Pulse','Spin','Motion path') else 'Entrance',trigger=sid)
            write_timeline(editor.deck.slides[0],[entry]);show=SlideShow(editor,0);player=show.timeline_player
            self.assertTrue(player.trigger(sid));group=player.running[-1];group.pause();group.setCurrentTime(group.totalDuration())
            self.assertTrue(player.items[sid].opacity()>0);show.close()
        slide=editor.deck.slides[0];before=slide._element.xml;editor.thumbnail(0);self.assertEqual(slide._element.xml,before)
        # Simulate a standard PowerPoint-created effect by removing only Dazzle metadata.
        ext=slide._element.find('.//{urn:drunkpeanuts:timeline:1}timeline');ext.getparent().getparent().remove(ext.getparent())
        self.assertEqual(timeline(slide)[0].effect,'Motion path')
        with self.assertRaises(ValueError):Effect(sid,duration=float('nan')).validate()
        with self.assertRaises(ValueError):motion_path('M 0 0 L 5000 0')
        with self.assertRaises(ValueError):motion_path('M 0 0 garbage L 1 1')
        self.assertAlmostEqual(motion_path('M .1 .2 l .2 .3 E').currentPosition().x(),.3)
        editor.dirty=False;editor.close()

    def test_composed_effects_and_deckcraft_math(self):
        from animation_math import PRESETS,sample,ease
        import math
        for name in PRESETS:
            for phase in ('Entrance','Emphasis','Exit'):
                for progress in (0,.25,.5,.75,1):
                    state=sample(name,phase,progress,'Left',1280,720,1.5)
                    self.assertTrue(all(math.isfinite(value) for key,value in state.items() if key!='clip'),name)
        self.assertEqual(ease(0,.3,.3),0);self.assertEqual(ease(1,.3,.3),1)
        editor=Dazzle();shape=editor.insert_shape();sid=shape.shape_id
        entries=[Effect(sid,'Fade',duration=1),Effect(sid,'Spin','Emphasis','With previous',duration=1,amount=180),Effect(sid,'Grow/shrink','Emphasis','With previous',duration=1,amount=2)]
        write_timeline(editor.deck.slides[0],entries);show=SlideShow(editor,0);player=show.timeline_player
        player.advance();group=player.running[-1];group.pause();group.setCurrentTime(500)
        item=player.items[sid]
        self.assertAlmostEqual(item.opacity(),.5);self.assertAlmostEqual(item.rotation(),90)
        self.assertAlmostEqual(item.transform().m11(),1.5)
        show.close();editor.dirty=False;editor.close()

    def test_timed_slides_skip_pending_clicks_and_blackout_pauses(self):
        from slide_transitions import write
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        editor=Dazzle();shape=editor.insert_shape();write_timeline(editor.deck.slides[0],[Effect(shape.shape_id,'Fade',duration=10)])
        write(editor.deck.slides[0],'None',advance=2);editor.add()
        show=SlideShow(editor,0);show.advance();group=show.timeline_player.running[-1]
        QTest.keyClick(show,Qt.Key_B);self.assertEqual(group.state(),group.State.Paused);self.assertFalse(show.advance_timer.isActive())
        QTest.keyClick(show,Qt.Key_B);self.assertEqual(group.state(),group.State.Running);self.assertTrue(show.advance_timer.isActive())
        show.advance_timer.timeout.emit();self.assertEqual(show.index,1)
        show.close();editor.dirty=False;editor.close()

    def test_native_timing_edits_preserve_graph_and_mask_repeat_playback(self):
        import copy
        from PySide6.QtCore import QPointF
        from slide_animation import save_sequence,NS
        editor=Dazzle();shape=editor.insert_shape();slide=editor.deck.slides[0]
        write_timeline(slide,[Effect(shape.shape_id,'Spin',phase='Emphasis',duration=1)])
        ext=slide._element.find('.//{urn:drunkpeanuts:timeline:1}timeline');ext.getparent().getparent().remove(ext.getparent())
        original=timeline(slide);changed=copy.deepcopy(original);changed[0].duration=2;changed[0].repeat=-1
        old_shape=shape._element;save_sequence(slide,changed,original)
        self.assertIs(slide.shapes[-1]._element,old_shape)
        self.assertEqual(timeline(slide)[0].repeat,-1);self.assertEqual(timeline(slide)[0].duration,2)
        self.assertEqual(slide._element.find('.//p:animRot',NS).get('by'),'21600000')
        show=SlideShow(editor,0);show.advance();group=show.timeline_player.running[-1]
        self.assertEqual(group.totalDuration(),-1);show.advance();self.assertEqual(group.state(),group.State.Stopped);show.close()
        save_sequence(slide,[],timeline(slide))
        for effect in ('Circle','Diamond'):
            write_timeline(slide,[Effect(shape.shape_id,effect,duration=1)])
            show=SlideShow(editor,0);player=show.timeline_player;item=player.items[shape.shape_id]
            player.advance();group=player.running[-1];group.pause();group.setCurrentTime(400)
            rect=item.boundingRect();self.assertTrue(item.shape().contains(rect.center()));self.assertFalse(item.shape().contains(QPointF(1,1)))
            group.setCurrentTime(1000);self.assertTrue(item.shape().contains(QPointF(1,1)));show.close()
        original=timeline(slide);ext=slide._element.find('.//{urn:drunkpeanuts:timeline:1}timeline');ext.getparent().getparent().remove(ext.getparent());original=timeline(slide)
        changed=copy.deepcopy(original);changed[0].effect='Wipe';save_sequence(slide,changed,original)
        self.assertEqual(len(timeline(slide)),1);self.assertEqual(timeline(slide)[0].effect,'Wipe')
        editor.dirty=False;editor.close()
    def test_imported_order_and_trigger_batches(self):
        import copy
        from slide_animation import save_sequence
        editor=Dazzle();a=editor.insert_shape();b=editor.insert_shape();slide=editor.deck.slides[0]
        write_timeline(slide,[Effect(a.shape_id,'Fade'),Effect(b.shape_id,'Circle')])
        ext=slide._element.find('.//{urn:drunkpeanuts:timeline:1}timeline');ext.getparent().getparent().remove(ext.getparent());original=timeline(slide)
        save_sequence(slide,list(reversed(copy.deepcopy(original))),original)
        self.assertEqual([entry.effect for entry in timeline(slide)],['Circle','Fade'])
        write_timeline(slide,[Effect(a.shape_id,'Fade',trigger=b.shape_id),Effect(a.shape_id,'Spin','Emphasis','After previous',trigger=b.shape_id),Effect(a.shape_id,'Fade','Exit',trigger=b.shape_id)])
        show=SlideShow(editor,0);player=show.timeline_player;self.assertEqual(len(player.triggered[b.shape_id]),2)
        player.trigger(b.shape_id);group=player.running[-1];group.pause();self.assertEqual(len(group.entries),2);group.setCurrentTime(group.totalDuration());player.trigger(b.shape_id)
        self.assertEqual(len(player.running[-1].entries),1);show.close();editor.dirty=False;editor.close()
    def test_delete_cleans_all_effect_types_and_keeps_other_objects(self):
        from presentation_tools import choose_many,delete_objects
        editor=Dazzle();a=editor.insert_shape();b=editor.insert_shape();slide=editor.deck.slides[0]
        write_timeline(slide,[Effect(a.shape_id,'Spin','Emphasis'),Effect(b.shape_id,'Circle')])
        choose_many(editor,[a]);delete_objects(editor)
        self.assertEqual([e.shape for e in timeline(slide)],[b.shape_id]);editor.undo()
        self.assertEqual(len(timeline(editor.deck.slides[0])),2);editor.dirty=False;editor.close()

if __name__=='__main__':unittest.main()
