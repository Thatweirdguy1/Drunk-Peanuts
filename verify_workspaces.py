"""Exercise every React/native workspace using isolated documents and settings."""
import json
import sys
import wave
import tempfile
from pathlib import Path
from unittest.mock import patch


def unexpected_warning(parent, title, message, *_):
    raise AssertionError(f'Unexpected native warning: {title}: {message}')


@patch('PySide6.QtWidgets.QMessageBox.warning', side_effect=unexpected_warning)
def run(owner, application, wait, folder, _warnings):
    from PySide6.QtCore import QCoreApplication, QEvent, QSettings
    from PySide6.QtGui import QTextCursor
    from PySide6.QtWidgets import QMessageBox
    from desktop_workspaces import install
    from office_suite import WORKSPACES
    from screenwriter import ScreenwriterWindow
    from watchit import WatchIT
    results=[]
    trace=Path(tempfile.gettempdir())/'DrunkPeanuts-workspace-check-trace.txt'
    def stage(message):
        with trace.open('a',encoding='utf-8') as stream:stream.write(message+'\n')
    trace.write_text('Starting workspace checks\n',encoding='utf-8')
    for tool in ('pages','tables','dazzle','organize','sketch','formulaic','writer','play'):
        stage(tool+': create')
        with patch('screenwriter.Path.home',return_value=Path(folder)), patch('screenwriter.QSettings',return_value=QSettings(str(Path(folder)/'writer.ini'),QSettings.IniFormat)):
            window=ScreenwriterWindow() if tool=='writer' else WatchIT(deferred=not getattr(sys,'frozen',False)) if tool=='play' else WORKSPACES[tool.title()]()
        install(owner,window,tool)
        window.show()
        bridge=window.frontend_bridge
        loaded=[];bridge.stateChanged.connect(loaded.append)
        wait(lambda:bool(loaded))
        def js(source):
            output=[];window.frontend.page().runJavaScript(source,lambda value:output.append(value))
            wait(lambda:bool(output));return output[0]
        wait(lambda:js('!!document.querySelector("[data-native-canvas]")'))
        wait(lambda:window.frontend_host.isVisible() and window.frontend_host.width()>200)
        wait(lambda:not js('document.body.innerText.includes("Design preview")'))
        assert js('document.querySelector("nav [aria-current=page]").title.startsWith('+json.dumps(tool.title())+')'),tool
        for width,height in ((1280,720),(1920,1080)):
            window.resize(width,height)
            wait(lambda:js('document.documentElement.scrollWidth <= innerWidth'))
            bridge.canvas(json.dumps([72,122,500,300]))
            assert window.frontend_host.width()==500
        actions=bridge.state()['actions']
        assert actions or tool=='play',tool
        stage(tool+': controls')
        if tool=='pages':
            window.editor.setPlainText('Harbor notes\nFirst light at the pier.')
            cursor=window.editor.textCursor();cursor.select(QTextCursor.Document);window.editor.setTextCursor(cursor)
            bold=next(a for a in actions if a['label']=='Bold')
            js('window.__nativeTest=true')
            bridge.trigger(bold['id'])
            assert window.editor.fontWeight()>=700
            window.path=Path(folder)/'Harbor notes.docx';window.save()
            from docx import Document
            assert 'First light' in '\n'.join(p.text for p in Document(window.path).paragraphs)
            assert not window.editor.document().isModified()
            window.open(window.path)
            assert bridge.state()['name']=='Harbor notes.docx' and bridge.state()['imported']
            assert not bridge.state()['saved']
        elif tool=='dazzle':
            wait(lambda:js('!![...document.images].find(i => i.alt.startsWith("Slide 1:") && i.naturalWidth > 0)'))
            assert window.slide_styles[0]['background']=='#f5f3eb'
            window.add()
            bridge.command('{"key":"select","value":0}')
            assert window.index==0
            assert {'Group','Ungroup','Format text','Presenter view','Export slide images','Animation pane','Preview animations','Masters and layouts','Theme colors and fonts','Draw freeform','Union shapes','Accessibility checks','Slide comments','Alternative text','Print slides / notes / handouts','Chart options','Custom show sequence'} <= {a['label'] for a in actions}
            first=window.insert_text('First step');second=window.insert_text('Second step')
            bridge.command('{"key":"size","value":28}')
            assert second.text_frame.paragraphs[0].font.size.pt==28
            from presentation_tools import choose_many,group_objects,selected
            choose_many(window,[first,second]);group_objects(window)
            assert len(selected(window))==1 and len(selected(window)[0].shapes)==2
            window.undo()
            from slide_animation import Effect,write_timeline
            from dazzle import SlideShow
            shape=window.deck.slides[0].shapes[-1]
            write_timeline(window.deck.slides[0],[Effect(shape.shape_id,'Fade',duration=1)])
            show=SlideShow(window,0);show.advance();animation=show.timeline_player.running[-1]
            animation.pause();animation.setCurrentTime(500)
            assert abs(show.timeline_player.items[shape.shape_id].opacity()-.5)<.01
            show.close()
        elif tool=='tables':
            window.grid.setCurrentCell(0,0)
            bridge.command(json.dumps(dict(key='formula',value='=2+3')))
            assert window.grid.item(0,0).text()=='=2+3'
            assert window.dirty
        elif tool=='writer':
            window.editor.setPlainText('EXT. HARBOR - DAWN\n\nMAYA\nListen to that.')
            bridge.command(json.dumps(dict(key='element',value=1)))
            assert window.element.currentIndex()==1
            assert window.autosave.is_relative_to(Path(folder))
            window.autosave_timer.stop();window.editor.document().setModified(False)
        elif tool=='sketch':
            bridge.command(json.dumps(dict(key='size',value=12)))
            bridge.command(json.dumps(dict(key='color',value='#9457ff')))
            assert window.canvas.pen_width==12 and window.canvas.color.name()=='#9457ff'
        elif tool=='play':
            if window.player is not None:
                track=Path(folder)/'Harbor room tone.wav'
                with wave.open(str(track),'wb') as stream:
                    stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(8000)
                    stream.writeframes(b'\0\0'*8000*20)
                window.add_media([track],autoplay=True)
                wait(lambda:window.player.is_playing())
            surface,handle=int(window.surface.winId()),int(window.winId())
            bridge.command('{"key":"volume","value":200}')
            assert window.volume.value()==200
            bridge.command('{"key":"pip"}');wait(lambda:js('!!document.querySelector(".player-controls.compact")'))
            assert int(window.surface.winId())==surface and int(window.winId())==handle
            bridge.command('{"key":"pip"}');wait(lambda:not js('!!document.querySelector(".player-controls.compact")'))
            bridge.command('{"key":"fullscreen"}');assert window.isFullScreen()
            window._show_controls(True)
            assert window.transport.isHidden() and window.seek.isHidden()
            window.escape_view();assert not window.isFullScreen()
            assert window.heading.isHidden() and window.statusBar().isHidden()
            if window.player is not None:assert window.player.is_playing()
        stage(tool+': cleanup')
        if hasattr(window,'dirty'):window.dirty=False
        if hasattr(window,'source'):window.source.document().setModified(False)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Discard):window.close()
        window.frontend.page().deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        window.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        results.append(tool)
        stage(tool+': passed')
    return results
