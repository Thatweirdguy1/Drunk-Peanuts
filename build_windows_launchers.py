"""Build small, separately named Windows Open With entry points (no extra runtime)."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from windows_integration import WORKSPACE_EXTENSIONS, launcher_name


def build(folder):
    compiler = next((p for p in (Path(os.environ['WINDIR'])/'Microsoft.NET'/arch/'v4.0.30319/csc.exe' for arch in ('Framework64','Framework')) if p.is_file()), None)
    if compiler is None:
        raise RuntimeError('The Windows .NET Framework C# compiler is required to build Open With launchers.')
    folder = Path(folder).resolve()
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary)/'Launcher.cs'
        for workspace in WORKSPACE_EXTENSIONS:
            arguments = '--play' if workspace == 'Play' else '--open-workspace ' + workspace
            source.write_text(r'''using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
[assembly:System.Reflection.AssemblyTitle("WORKSPACE · Drunk Peanuts")]
class Launcher {
  static string Quote(string value) {
    var result = new System.Text.StringBuilder("\"");
    int slashes = 0;
    foreach(char c in value) {
      if(c == '\\') { slashes++; continue; }
      result.Append('\\', c == '"' ? slashes * 2 + 1 : slashes);
      result.Append(c); slashes = 0;
    }
    return result.Append('\\', slashes * 2).Append('"').ToString();
  }
  [STAThread] static void Main(string[] args) {
    try {
      var info = new ProcessStartInfo(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "LocalFileConverter.exe"));
      info.UseShellExecute = false;
      info.Arguments = "ARGUMENTS";
      foreach (string arg in args) info.Arguments += " " + Quote(arg);
      Process.Start(info);
    } catch(Exception error) { MessageBox.Show(error.Message, "Drunk Peanuts"); }
  }
}'''.replace('WORKSPACE', workspace).replace('ARGUMENTS', arguments), encoding='utf-8')
            subprocess.run([str(compiler), '/nologo', '/target:winexe', '/reference:System.Windows.Forms.dll', '/win32icon:assets/app.ico', '/out:'+str(folder/launcher_name(workspace)), str(source)], check=True)


if __name__ == '__main__':
    build(sys.argv[1])
