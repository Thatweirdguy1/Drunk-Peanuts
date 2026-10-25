"""Per-user Windows registration; never changes the user's default player."""
from pathlib import Path
import sys

MEDIA_EXTENSIONS = ('.mp4', '.mkv', '.mov', '.avi', '.webm', '.mpeg', '.mpg', '.wmv', '.m4v', '.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.aiff', '.wma')


def registration_values(executable):
    executable = str(Path(executable).resolve())
    command = f'"{executable}" --play "%1"'
    classes = 'Software\\Classes\\'
    values = [
        (classes + 'FreeConvert.Media', '', 'Play · FreeConvert'),
        (classes + 'FreeConvert.Media\\DefaultIcon', '', f'"{executable}",0'),
        (classes + 'FreeConvert.Media\\shell\\open\\command', '', command),
        (classes + 'Applications\\LocalFileConverter.exe', 'FriendlyAppName', 'Play · FreeConvert'),
        (classes + 'Applications\\LocalFileConverter.exe\\shell\\open\\command', '', command),
        ('Software\\FreeConvert\\Capabilities', 'ApplicationName', 'FreeConvert'),
        ('Software\\FreeConvert\\Capabilities', 'ApplicationDescription', 'Local conversion, Office Suite and Play media player'),
        ('Software\\RegisteredApplications', 'FreeConvert', 'Software\\FreeConvert\\Capabilities'),
        ('Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\LocalFileConverter.exe', '', executable),
    ]
    for extension in MEDIA_EXTENSIONS:
        values.extend([
            (classes + extension + '\\OpenWithProgids', 'FreeConvert.Media', ''),
            (classes + 'Applications\\LocalFileConverter.exe\\SupportedTypes', extension, ''),
            ('Software\\FreeConvert\\Capabilities\\FileAssociations', extension, 'FreeConvert.Media'),
        ])
    return values


def register(executable=None):
    if sys.platform != 'win32':
        raise OSError('Windows registration is only available on Windows')
    import ctypes
    import winreg
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
    owned = ('Software\\Classes\\FreeConvert.Media', 'Software\\Classes\\Applications\\LocalFileConverter.exe', 'Software\\FreeConvert', 'Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\LocalFileConverter.exe')
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
