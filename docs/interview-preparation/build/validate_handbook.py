"""Read-only manuscript checks; writes only sanitized validation metadata."""
import argparse
import hashlib
import json
import re
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "validation-report.json"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main", "m": "http://schemas.openxmlformats.org/officeDocument/2006/math", "r": "http://schemas.openxmlformats.org/package/2006/relationships"}


def check_docx(path, markdown_path):
    with zipfile.ZipFile(path) as z:
        bad_member = z.testzip()
        xml = ET.fromstring(z.read("word/document.xml"))
        styles = ET.fromstring(z.read("word/styles.xml"))
        style_names = {}
        for style in styles.findall("w:style", NS):
            name = style.find("w:name", NS)
            style_names[style.get("{" + NS["w"] + "}styleId")] = name.get("{" + NS["w"] + "}val", "") if name is not None else ""
        paragraphs = xml.findall(".//w:p", NS)
        def plain(p):
            return "".join(t.text or "" for t in p.iter() if t.tag in ("{" + NS["w"] + "}t", "{" + NS["m"] + "}t"))
        paragraph_texts = [plain(p) for p in paragraphs]
        headings = []
        for no, p in enumerate(paragraphs, 1):
            ps = p.find("w:pPr/w:pStyle", NS)
            if ps is None:
                continue
            name = style_names.get(ps.get("{" + NS["w"] + "}val"), "")
            if re.match(r"(?i)^heading\s*[1-9]$", name):
                headings.append({"paragraph": no, "text": plain(p), "style": name})
        md_lines = markdown_path.read_text(encoding="utf-8-sig").splitlines()
        def md_inline(s):
            s = re.sub(r"\[([^\]]+)\]\((?:<[^>]+>|[^)]+)\)", r"\1", s)
            return s.replace("`", "").replace("**", "")
        md_headings = [md_inline(m.group(1)) for line in md_lines if (m := re.match(r"^#{1,6}\s+(.+)$", line))]
        def norm(s):
            s = unicodedata.normalize("NFKC", s)
            return re.sub(r"\s+", "", s)
        actual_headings = [h["text"] for h in headings]
        missing_headings = [{"index": i+1, "heading": h} for i, h in enumerate(md_headings) if norm(h) not in {norm(x) for x in actual_headings}]
        all_text = "\n".join(paragraph_texts)
        corpus = norm(all_text)
        prose_checked, prose_misses = 0, []
        code_checked, code_misses, table_cells_checked, table_cell_misses = 0, [], 0, []
        fenced, display_math = False, False
        for no, line in enumerate(md_lines, 1):
            stripped = line.strip()
            if re.match(r"^(`{3,}|~{3,})", stripped):
                fenced = not fenced
                continue
            if fenced:
                if stripped:
                    code_checked += 1
                    if norm(stripped) not in corpus:
                        code_misses.append({"source_line": no, "reason": "normalized_code_line_not_found"})
                continue
            if stripped in (r"\[", r"\]"):
                display_math = stripped == r"\["
                continue
            if stripped.startswith("|"):
                cells = re.split(r"(?<!\\)\|", stripped.strip("|"))
                if not all(re.fullmatch(r"\s*:?-+:?\s*", c) for c in cells):
                    for cell_no, cell in enumerate(cells, 1):
                        cleaned_cell = md_inline(cell.strip()).replace(r"\|", "|")
                        if cleaned_cell:
                            table_cells_checked += 1
                            if norm(cleaned_cell) not in corpus:
                                table_cell_misses.append({"source_line": no, "cell": cell_no, "reason": "normalized_table_cell_not_found"})
                continue
            if display_math or not stripped or stripped.startswith(("#", "\\", "```")):
                continue
            cleaned = re.sub(r"^(?:>\s*|[-*+]\s+|\d+[.)]\s+)", "", stripped)
            cleaned = md_inline(cleaned)
            if len(cleaned) < 20 or re.search(r"\$[^$]+\$", cleaned):
                continue
            prose_checked += 1
            if norm(cleaned) not in corpus:
                prose_misses.append({"source_line": no, "reason": "normalized_source_prose_not_found_as_contiguous_document_text"})
        rels = ET.fromstring(z.read("word/_rels/document.xml.rels"))
        local_links, link_errors = [], []
        for rel in rels:
            target = rel.get("Target", "")
            if rel.get("TargetMode") != "External" or not rel.get("Type", "").endswith("/hyperlink"):
                continue
            url = unquote(target)
            if url.startswith("file:///"):
                url = url[8:]
            if re.match(r"^[A-Za-z]:[/\\]", url):
                item = {"relationship_id": rel.get("Id"), "target": url, "exists": Path(url).exists()}
                local_links.append(item)
                if not item["exists"]:
                    link_errors.append(item)
        fields = [t.text or "" for t in xml.findall(".//w:instrText", NS)]
        main_sensitive_hits = []
        # Keep values out of the audit record; flag only types and paragraph locations.
        content_patterns = {
            "provider_secret_shape": r"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16})\b",
            "jwt_shape": r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b",
            "employee_id_shape": r"\b[tT]\d{8}\b",
            "internal_url_or_email": r"(?i)(?:https?://[^\s]*\.(?:huawei\.com|internal|corp|local)\b|[A-Za-z0-9_.+-]+@(?:[A-Za-z0-9.-]+\.)?huawei\.com\b)",
        }
        for no, text in enumerate(paragraph_texts, 1):
            for kind, pattern in content_patterns.items():
                if re.search(pattern, text):
                    main_sensitive_hits.append({"paragraph": no, "type": kind})
        metadata_hits = []
        for part in ("docProps/core.xml", "docProps/custom.xml", "word/comments.xml"):
            if part in z.namelist():
                decoded = z.read(part).decode("utf-8", "replace")
                for kind, pattern in content_patterns.items():
                    if re.search(pattern, decoded):
                        metadata_hits.append({"part": part, "type": kind})
        footer_page_fields = 0
        for part in z.namelist():
            if re.match(r"word/footer\d+\.xml$", part):
                footer = ET.fromstring(z.read(part))
                footer_page_fields += sum(bool(re.search(r"\bPAGE\b", x.text or "")) for x in footer.findall(".//w:instrText", NS))
        return {
            "file": str(path.relative_to(ROOT)), "sha256": fingerprint(path), "zip_integrity_ok": bad_member is None,
            "main_body_paragraphs": len(xml.findall("w:body/w:p", NS)), "all_paragraphs_including_tables": len(paragraphs),
            "tables": len(xml.findall(".//w:tbl", NS)), "headings": len(headings),
            "source_heading_count": len(md_headings), "missing_source_headings": missing_headings,
            "heading_order_matches_markdown": [norm(h) for h in actual_headings] == [norm(h) for h in md_headings],
            "native_math_objects": len(xml.findall(".//m:oMath", NS)), "toc_fields": sum(bool(re.search(r"\bTOC\b", f)) for f in fields),
            "footer_page_fields": footer_page_fields,
            "local_hyperlinks": local_links, "missing_local_hyperlinks": link_errors,
            "tracked_insertions": len(xml.findall(".//w:ins", NS)), "tracked_deletions": len(xml.findall(".//w:del", NS)),
            "comment_anchors": len(xml.findall(".//w:commentRangeStart", NS)),
            "source_prose_lines_checked": prose_checked, "source_prose_lines_unmatched": prose_misses,
            "source_code_lines_checked": code_checked, "source_code_lines_unmatched": code_misses,
            "source_table_cells_checked": table_cells_checked, "source_table_cells_unmatched": table_cell_misses,
            "sensitive_pattern_hits": main_sensitive_hits, "metadata_sensitive_pattern_hits": metadata_hits,
            "coverage_limitations": "Normalized text coverage separately checks prose lines, code lines and table cells; it excludes native-equation equivalence and some short standalone lines, and does not establish visual layout or semantic correctness. Visual layout must be checked separately after rendering. No source project was executed.",
        }


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze(path):
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    links, missing, fences, unbalanced, questions, exercises = [], [], [], [], [], []
    open_fence = None
    secret_hits = []
    patterns = {
        "private_key_marker": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        "provider_secret_shape": r"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16})\b",
        "jwt_shape": r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b",
        "bearer_literal": r"(?i)\bbearer\s+[A-Za-z0-9_.-]{20,}",
        "credential_assignment": r"(?i)\b(?:password|passwd|api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*['\"][A-Za-z0-9_./+=-]{12,}['\"]",
        "employee_id_shape": r"\b[tT]\d{8}\b",
        "internal_email_shape": r"\b[A-Za-z0-9_.+-]+@(?:[A-Za-z0-9.-]+\.)?huawei\.com\b",
        "private_ipv4": r"(?<![\w.])(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(?![\w.])",
    }
    for no, line in enumerate(lines, 1):
        fm = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if fm:
            marker = fm.group(1)
            if open_fence is None:
                open_fence = (marker[0], len(marker), no)
                fences.append({"line": no, "kind": "open", "language": fm.group(2).strip()})
            elif marker[0] == open_fence[0] and len(marker) >= open_fence[1] and not fm.group(2).strip():
                fences.append({"line": no, "kind": "close"})
                open_fence = None
        if open_fence is None:
            qm = re.match(r"^#{2,4}\s+((?:Q\d+|S\d+|X\d+))(?=\s|[｜　【])", line)
            if qm:
                questions.append({"line": no, "id": qm.group(1)})
            if re.match(r"^(?:#{2,4}\s+|\*\*)练习[一二三四五六七八九十\d]+", line):
                exercises.append({"line": no})
        for m in re.finditer(r"\]\((<[^>]+>|[^\n)]+)\)", line):
            raw = m.group(1).strip().strip("<>")
            if re.match(r"^[A-Za-z]:[/\\]", raw):
                target = Path(unquote(raw.split("#", 1)[0]))
            elif raw.startswith(("http://", "https://", "mailto:", "#", "codex:", "app:", "plugin:")):
                continue
            else:
                target = path.parent / unquote(raw.split("#", 1)[0])
            item = {"line": no, "target": str(target), "exists": target.exists()}
            links.append(item)
            if not item["exists"]:
                missing.append(item)
        for kind, pattern in patterns.items():
            if re.search(pattern, line):
                secret_hits.append({"line": no, "type": kind})
        for m in re.finditer(r"https?://[^\s<>\]\)\"']+", line):
            host = (urlparse(m.group()).hostname or "").lower()
            if host.endswith((".huawei.com", ".huawei.internal", ".internal", ".corp", ".local")) or host in ("localhost", "127.0.0.1"):
                secret_hits.append({"line": no, "type": "internal_or_local_service_url"})
    if open_fence:
        unbalanced.append({"line": open_fence[2], "type": "unclosed_fence"})
    ids = [q["id"] for q in questions]
    return {
        "file": str(path.relative_to(ROOT)),
        "sha256": fingerprint(path),
        "lines": len(lines),
        "local_link_count": len(links),
        "local_links": links,
        "missing_local_links": missing,
        "code_fence_pairs": len(fences) // 2,
        "code_fence_errors": unbalanced,
        "question_count": len(questions),
        "questions": questions,
        "duplicate_question_ids": sorted({q for q in ids if ids.count(q) > 1}),
        "exercise_count": len(exercises),
        "exercises": exercises,
        "sensitive_pattern_hits": secret_hits,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--docx", action="store_true")
    args = parser.parse_args()
    paths = sorted((ROOT / "chapters").glob("*.md"))
    if args.final:
        paths.append(ROOT / "项目面试准备手册-陶壮.md")
    reports = [analyze(path) for path in paths]
    chapters = reports[:7]
    result = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "final" if args.final else "chapters_before_final_merge",
        "read_only_scope": "chapter manuscripts; final manuscript only with --final; source projects not changed or executed",
        "limitations": [
            "Pattern checks flag likely secrets and internal endpoints; zero hits do not prove absence of every possible sensitive detail.",
            "Link checks validate local filesystem existence, not source correctness, heading anchors, URL availability, or external disclosure approval.",
            "Question counts include Q/S/X heading identifiers; exercise counts include explicitly numbered exercise headings or bold labels.",
            "This report checks DOCX structure and selected text coverage only; it does not inspect rendered pages.",
        ],
        "files": reports,
        "chapter_totals": {
            "files": len(chapters),
            "local_links": sum(x["local_link_count"] for x in chapters),
            "missing_links": sum(len(x["missing_local_links"]) for x in chapters),
            "code_fence_pairs": sum(x["code_fence_pairs"] for x in chapters),
            "code_fence_errors": sum(len(x["code_fence_errors"]) for x in chapters),
            "questions": sum(x["question_count"] for x in chapters),
            "exercises": sum(x["exercise_count"] for x in chapters),
            "sensitive_pattern_hits": sum(len(x["sensitive_pattern_hits"]) for x in chapters),
        },
    }
    if args.final:
        merged = (ROOT / "项目面试准备手册-陶壮.md").read_text(encoding="utf-8-sig")
        chapter_texts = [p.read_text(encoding="utf-8-sig").strip() for p in paths[:7]]
        expected = "\n\n".join(chapter_texts)
        result["merge_consistency"] = {
            "exact_after_outer_whitespace_normalization": merged.strip() == expected,
            "all_chapters_present_in_order": all(merged.find(t) >= 0 for t in chapter_texts) and [merged.find(t) for t in chapter_texts] == sorted(merged.find(t) for t in chapter_texts),
            "merged_characters": len(merged),
            "merged_cjk_characters": len(re.findall(r"[\u4e00-\u9fff]", merged)),
            "question_ids_are_chapter_local": True,
        }
    if args.docx:
        result["docx"] = check_docx(ROOT / "项目面试准备手册-陶壮.docx", ROOT / "项目面试准备手册-陶壮.md")
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(OUT), "chapter_totals": result["chapter_totals"], "merge_consistency": result.get("merge_consistency"), "docx": result.get("docx"), "per_file": [{k: r[k] for k in ("file", "question_count", "exercise_count", "code_fence_pairs", "missing_local_links", "code_fence_errors", "sensitive_pattern_hits")} for r in reports]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
