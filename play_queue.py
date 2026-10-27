"""Local-only playlist files, folder expansion and same-user Play requests."""
import getpass
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from PySide6.QtCore import QObject, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from windows_integration import MEDIA_EXTENSIONS, PLAYLIST_EXTENSIONS
SERVER_NAME = 'DrunkPeanuts.Play.' + hashlib.sha256(getpass.getuser().encode()).hexdigest()[:16]


def media_paths(names, cancelled=lambda: False):
    """Expand local folders/playlists in order; never execute playlist directives."""
    files, seen_lists = [], set()

    def visit(path, depth=0):
        if cancelled():
            return
        path = Path(path)
        if path.is_symlink():
            return
        if depth > 20:
            return
        path = path.resolve()
        if path.is_dir():
            for root, dirs, names in os.walk(path, followlinks=False, onerror=lambda error: None):
                if cancelled():
                    return
                dirs[:] = sorted(d for d in dirs if not (Path(root)/d).is_symlink())
                for name in sorted(names, key=str.casefold):
                    child = Path(root)/name
                    if child.suffix.lower() in MEDIA_EXTENSIONS:
                        visit(child)
        elif path.is_file() and path.suffix.lower() in PLAYLIST_EXTENSIONS:
            if path in seen_lists:
                return
            seen_lists.add(path)
            if path.stat().st_size > 1024 * 1024:
                raise ValueError('Playlist is larger than 1 MB. Split it into smaller lists.')
            for line in path.read_text(encoding='utf-8-sig', errors='replace').splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('file:'):
                    url = urlparse(line)
                    if url.netloc not in ('', 'localhost'):
                        continue
                    line = unquote(url.path)
                    if os.name == 'nt' and len(line) > 2 and line[0] == '/' and line[2] == ':':
                        line = line[1:]
                elif '://' in line:
                    continue
                target = Path(line)
                visit(target if target.is_absolute() else path.parent/target, depth + 1)
        elif path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS:
            files.append(path)

    for name in names:
        visit(name)
    return files


def save_playlist(path, files):
    path = Path(path)
    # Atomic replacement protects an existing list if writing fails.
    import tempfile
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write('#EXTM3U\n')
            for item in files:
                output.write(Path(item).resolve().as_uri() + '\n')
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def forward_play(names, enqueue=False):
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if not socket.waitForConnected(350):
        return False
    payload = json.dumps({'paths': [str(Path(p).resolve()) for p in names], 'enqueue': enqueue}).encode() + b'\n'
    if len(payload) > 1024 * 1024:
        raise ValueError('Too many playlist inputs')
    socket.write(payload)
    socket.waitForBytesWritten(2000)
    # Only exit after the receiving app acknowledges the complete request.
    received = socket.waitForReadyRead(3000) and bytes(socket.readAll()) == b'OK'
    socket.disconnectFromServer()
    return bool(received)


class PlayInbox(QObject):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.UserAccessOption)
        self.callback = callback
        self.server.newConnection.connect(self._accept)
        if not self.server.listen(SERVER_NAME):
            probe = QLocalSocket()
            probe.connectToServer(SERVER_NAME)
            if not probe.waitForConnected(200):
                QLocalServer.removeServer(SERVER_NAME)
                self.server.listen(SERVER_NAME)
            probe.abort()

    def _accept(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            buffer = bytearray()
            def read(socket=socket, buffer=buffer):
                buffer.extend(bytes(socket.readAll()))
                if len(buffer) > 1024 * 1024:
                    socket.abort()
                    return
                if b'\n' not in buffer:
                    return
                try:
                    request = json.loads(buffer.split(b'\n', 1)[0])
                    if not isinstance(request, dict) or not isinstance(request.get('paths'), list) or not all(isinstance(p, str) for p in request['paths']) or type(request.get('enqueue')) is not bool:
                        raise ValueError('Invalid Play request')
                except (ValueError, TypeError):
                    socket.abort()
                    return
                socket.readyRead.disconnect(read)
                try:
                    self.callback(request['paths'], request['enqueue'])
                except (OSError, ValueError):
                    socket.abort()
                    return
                socket.write(b'OK')
                socket.disconnectFromServer()
            socket.readyRead.connect(read)
            socket.disconnected.connect(socket.deleteLater)
            QTimer.singleShot(5000, socket, socket.abort)
            read()
