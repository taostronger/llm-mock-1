"""Locate managed document dependencies without embedding machine identities."""
from __future__ import annotations
import os
from pathlib import Path
import shutil

RUNTIME = Path(os.environ.get("CODEX_MANUAL_RUNTIME", Path.home()/".cache/codex-runtimes/codex-primary-runtime")).expanduser()
WINDOWS = os.name == "nt"
PY = RUNTIME/("dependencies/python/python.exe" if WINDOWS else "dependencies/python/bin/python")
NODE = RUNTIME/("dependencies/node/bin/node.exe" if WINDOWS else "dependencies/node/bin/node")
PANDOC = Path(os.environ.get("CODEX_MANUAL_PANDOC") or shutil.which("pandoc") or Path.home()/"AppData/Local/Pandoc/pandoc.exe")
POPLER = Path(os.environ.get("CODEX_MANUAL_POPPLER", RUNTIME/"dependencies/native/poppler/Library/bin"))
PWSH = Path(os.environ.get("CODEX_MANUAL_PWSH") or str(RUNTIME/"dependencies/native/powershell/pwsh.exe"))

def find_renderer() -> Path | None:
    override = os.environ.get("CODEX_MANUAL_RENDERER")
    if override:
        return Path(override).expanduser()
    cache = Path.home()/".codex/plugins/cache/openai-primary-runtime/documents"
    matches = sorted(cache.glob("*/skills/documents/render_docx.py"))
    return matches[-1] if matches else None

RENDERER = find_renderer()

def require_file(path: Path | None, name: str, hint: str) -> Path:
    if path is None or not path.is_file():
        raise FileNotFoundError(f"{name} was not found. {hint}")
    return path
