"""Use the installed renderer with Word COM as its PDF conversion backend.

Only this process replaces convert_to_pdf; the installed renderer is unchanged.
The renderer and Poppler are external managed dependencies, not vendored here.
"""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import subprocess
from runtime_config import RENDERER, POPLER, PWSH, WINDOWS, require_file

BUILD = Path(__file__).resolve().parent
os.environ["PATH"] = str(POPLER)+os.pathsep+os.environ.get("PATH", "")
os.environ["PYTHONIOENCODING"] = "utf-8"

def word_convert(doc_path: str, user_profile: str, convert_tmp_dir: str, stem: str, verbose: bool) -> tuple[str, str]:
    output = Path(convert_tmp_dir)/(stem+".pdf")
    cmd = [str(PWSH), "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
        str(BUILD/"word_export.ps1"), "-InputDocx", str(Path(doc_path).resolve()), "-PdfPath", str(output)]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=1200, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    log = f"ENGINE: Microsoft Word COM\nEXIT: {result.returncode}\n{result.stdout}\n{result.stderr}"
    if verbose:
        print(log)
    if result.returncode or not output.is_file() or not output.stat().st_size:
        return "", log
    return str(output), log

def main():
    if not WINDOWS:
        raise RuntimeError("Word COM rendering requires Windows and Microsoft Word.")
    require_file(RENDERER, "Managed render_docx.py", "Set CODEX_MANUAL_RENDERER to the installed renderer file.")
    require_file(PWSH, "PowerShell", "Set CODEX_MANUAL_PWSH to pwsh.exe or powershell.exe.")
    spec = importlib.util.spec_from_file_location("managed_docx_renderer", RENDERER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load the configured renderer")
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    renderer.convert_to_pdf = word_convert
    renderer.main()

if __name__ == "__main__":
    main()
