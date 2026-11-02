"""Build the interview handbook using configurable managed document tools.

Run with the managed Python. --render requires Windows, Word and an available
managed render_docx.py. --smoke renders a small standalone layout specimen.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import subprocess
from runtime_config import PY, NODE, PANDOC, RENDERER, POPLER, WINDOWS, require_file

BUILD = Path(__file__).resolve().parent
ROOT = BUILD.parent

def call(args, log, check=True):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    env["PATH"] = str(POPLER)+os.pathsep+env.get("PATH", "")
    result = subprocess.run([str(v) for v in args], cwd=BUILD, env=env,
        text=True, capture_output=True, encoding="utf-8", errors="replace",
        timeout=1800, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    (BUILD/log).write_text(result.stdout+"\n"+result.stderr, encoding="utf-8")
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode and check:
        raise RuntimeError(f"Command failed ({result.returncode}); see {BUILD/log}")
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT/"项目面试准备手册-陶壮.md")
    parser.add_argument("--output", type=Path, default=ROOT/"项目面试准备手册-陶壮.docx")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--qa-dir", type=Path)
    args = parser.parse_args()
    require_file(PY, "Managed Python", "Set CODEX_MANUAL_RUNTIME to the managed runtime root.")
    require_file(NODE, "Managed Node", "Set CODEX_MANUAL_RUNTIME to the managed runtime root.")
    require_file(PANDOC, "Pandoc", "Install Pandoc or set CODEX_MANUAL_PANDOC to its executable.")
    if args.smoke:
        args.input = BUILD/"smoke.md"
        args.output = BUILD/"smoke.docx"
        args.render = True
    if args.render:
        if not WINDOWS:
            raise RuntimeError("The Word rendering fallback requires Windows and Microsoft Word. Omit --render to build the DOCX only.")
        require_file(RENDERER, "Managed render_docx.py", "Set CODEX_MANUAL_RENDERER to an installed renderer; it is not bundled here.")
    if not args.input.is_file():
        raise FileNotFoundError(args.input)
    reference = BUILD/"reference.docx"
    call([NODE, BUILD/"create_reference.cjs", reference], "reference.log")
    raw = BUILD/("smoke.raw.docx" if args.smoke else "manual.raw.docx")
    call([PANDOC, args.input.resolve(), "--from", "markdown+tex_math_dollars+tex_math_single_backslash+pipe_tables+fenced_code_blocks",
        "--to", "docx", "--standalone", "--toc", "--toc-depth", "2", "--reference-doc", reference,
        "--metadata", "title=大模型项目面试准备手册", "--metadata", "subtitle=核心原理 实现细节 深入追问",
        "--metadata", "author=陶壮", "--metadata", "date=2026-11-02", "--output", raw], "pandoc.log")
    args.output = args.output.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    call([PY, BUILD/"polish_docx.py", raw, args.output], "polish.log")
    if args.render:
        qa = (args.qa_dir or BUILD/("smoke-pages" if args.smoke else "manual-pages")).resolve()
        if qa.is_relative_to(BUILD.resolve()) and qa.is_dir():
            for old in qa.glob("page-*.png"):
                old.unlink()
        diagnostic = BUILD/"normal-render-diagnostic.log"
        if not diagnostic.exists():
            normal = call([PY, RENDERER, args.output, "--output_dir", BUILD/"normal-render-attempt", "--dpi", "130", "--emit_pdf"], diagnostic.name, check=False)
            print("Original renderer return code:", normal.returncode)
        call([PY, BUILD/"render_with_word.py", args.output, "--output_dir", qa, "--dpi", "140", "--emit_pdf", "--verbose"], "word-render.log")
        print("QA pages:", qa)
    print("DOCX:", args.output)

if __name__ == "__main__":
    main()
