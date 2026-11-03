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

if __name__=='__main__':unittest.main()
