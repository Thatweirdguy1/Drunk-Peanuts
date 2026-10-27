"""Per-user Windows registration; never changes the user's default player."""
from pathlib import Path
import sys

MEDIA_EXTENSIONS = ('.mp4', '.mkv', '.mov', '.avi', '.webm', '.mpeg', '.mpg', '.wmv', '.m4v', '.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.aiff', '.wma')
PLAYLIST_EXTENSIONS = ('.m3u', '.m3u8')
WORKSPACE_EXTENSIONS = {
    'Pages': ('.docx', '.txt', '.html', '.htm'),
    'Tables': ('.xlsx', '.csv'),
    'Dazzle': ('.pptx', '.dazzle'),
    'Sketch': ('.png', '.jpg', '.jpeg', '.bmp'),
    'Organize': ('.sqlite', '.db'),
    'Formulaic': ('.formulaic', '.mml'),
    'Writer': ('.fountain', '.fdx'),
    'Play': MEDIA_EXTENSIONS + PLAYLIST_EXTENSIONS,
}


def launcher_name(workspace):
    return f'DrunkPeanuts.{workspace}.exe'


def registration_values(executable):
    executable = str(Path(executable).resolve())
    command = f'"{executable}" --play "%1"'
    classes = 'Software\\Classes\\'
    values = [
        (classes + 'FreeConvert.Media', '', 'Play · Drunk Peanuts'),
        (classes + 'FreeConvert.Media\\DefaultIcon', '', f'"{executable}",0'),
        (classes + 'FreeConvert.Media\\shell\\open\\command', '', command),
        (classes + 'Applications\\LocalFileConverter.exe', 'FriendlyAppName', 'Play · Drunk Peanuts'),
        (classes + 'Applications\\LocalFileConverter.exe\\shell\\open\\command', '', command),
        ('Software\\FreeConvert\\Capabilities', 'ApplicationName', 'Drunk Peanuts'),
        ('Software\\FreeConvert\\Capabilities', 'ApplicationDescription', 'Local conversion, Office Suite and Play media player'),
        ('Software\\RegisteredApplications', 'FreeConvert', 'Software\\FreeConvert\\Capabilities'),
        ('Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\LocalFileConverter.exe', '', executable),
        # Keep legacy defaults launchable; only the dedicated Play launcher is offered.
        (classes + 'FreeConvert.Media', 'NoOpenWith', ''),
        (classes + 'Applications\\LocalFileConverter.exe', 'NoOpenWith', ''),
    ]
    for verb, title, argument in (('DrunkPeanuts.Play', 'Play with Drunk Peanuts Play', '--play'),
                                  ('DrunkPeanuts.Enqueue', 'Add to Drunk Peanuts Play playlist', '--enqueue')):
        key = classes + 'Directory\\shell\\' + verb
        values.extend([(key, '', title), (key, 'Icon', f'"{executable}",0'),
                       (key, 'MultiSelectModel', 'Player'),
                       (key + '\\command', '', f'"{executable}" {argument} "%1"')])
    for extension in MEDIA_EXTENSIONS:
        values.extend([
            (classes + extension + '\\OpenWithProgids', 'FreeConvert.Media', ''),
            (classes + 'Applications\\LocalFileConverter.exe\\SupportedTypes', extension, ''),
            ('Software\\FreeConvert\\Capabilities\\FileAssociations', extension, 'FreeConvert.Media'),
        ])
    for workspace, extensions in WORKSPACE_EXTENSIONS.items():
        launcher = str(Path(executable).parent / launcher_name(workspace))
        progid = 'DrunkPeanuts.' + workspace
        application = classes + 'Applications\\' + launcher_name(workspace)
        capabilities = 'Software\\DrunkPeanuts\\' + workspace + '\\Capabilities'
        title = workspace + ' · Drunk Peanuts'
        values.extend([
            (classes + progid, '', title),
            (classes + progid + '\\DefaultIcon', '', f'"{launcher}",0'),
            (classes + progid + '\\shell\\open\\command', '', f'"{launcher}" "%1"'),
            (classes + progid + '\\Application', 'ApplicationName', title),
            (application, 'FriendlyAppName', title),
            (application + '\\shell\\open\\command', '', f'"{launcher}" "%1"'),
            (capabilities, 'ApplicationName', title),
            (capabilities, 'ApplicationDescription', 'Offline ' + workspace + ' workspace'),
            ('Software\\RegisteredApplications', progid, capabilities),
        ])
        for extension in extensions:
            values.extend([
                (classes + extension + '\\OpenWithProgids', progid, ''),
                (application + '\\SupportedTypes', extension, ''),
                (capabilities + '\\FileAssociations', extension, progid),
            ])
    return values


def register(executable=None):
    if sys.platform != 'win32':
        raise OSError('Windows registration is only available on Windows')
    import ctypes
    import winreg
    folder = Path(executable or sys.executable).resolve().parent
    missing = [launcher_name(w) for w in WORKSPACE_EXTENSIONS if not (folder / launcher_name(w)).is_file()]
    if missing:
        raise FileNotFoundError('Open With launchers are missing; reinstall the complete app: ' + ', '.join(missing))
    for path, name, value in registration_values(executable or sys.executable):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)


def unregister(executable=None):
    import ctypes
    import winreg
    values = registration_values(executable or sys.executable)
    # An older installation must not remove a newer installation's registration.
    command_key = 'Software\\Classes\\FreeConvert.Media\\shell\\open\\command'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, command_key) as key:
            if winreg.QueryValueEx(key, '')[0] != values[2][2]:
                return
    except FileNotFoundError:
        return
    for path, name, value in values:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_ALL_ACCESS) as key:
                if winreg.QueryValueEx(key, name)[0] == value:
                    winreg.DeleteValue(key, name)
        except FileNotFoundError:
            pass
    owned = ('Software\\Classes\\Directory\\shell\\DrunkPeanuts.Play', 'Software\\Classes\\Directory\\shell\\DrunkPeanuts.Enqueue',
             'Software\\Classes\\FreeConvert.Media', 'Software\\Classes\\Applications\\LocalFileConverter.exe', 'Software\\FreeConvert', 'Software\\DrunkPeanuts', 'Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\LocalFileConverter.exe',
             *(f'Software\\Classes\\DrunkPeanuts.{w}' for w in WORKSPACE_EXTENSIONS),
             *(f'Software\\Classes\\Applications\\{launcher_name(w)}' for w in WORKSPACE_EXTENSIONS))
    paths = set()
    for path, _, _ in values:
        for prefix in owned:
            if path == prefix or path.startswith(prefix + '\\'):
                while len(path) >= len(prefix):
                    paths.add(path)
                    path = path.rsplit('\\', 1)[0]
    for path in sorted(paths, key=len, reverse=True):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                children, entries, _ = winreg.QueryInfoKey(key)
            if not children and not entries:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
        except FileNotFoundError:
            pass
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
