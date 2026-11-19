"""极简 Markdown → 可打印 HTML（仅覆盖本项目报告用到的语法）。

支持：标题、段落、无序/有序列表、表格、围栏代码块、引用、分隔线、
     行内 **粗体**、`代码`、[链接](url)。

用法：python tools/md2html.py report/项目总结.md report/项目总结.html "标题"
"""

from __future__ import annotations

import html
import os
import re
import sys

CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body {
  font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", system-ui, sans-serif;
  font-size: 10.5pt; line-height: 1.62; color: #1f2430; margin: 0 auto;
  max-width: 190mm; padding: 8mm 0 16mm;
}
h1 { font-size: 20pt; margin: 0 0 6pt; padding-bottom: 6pt; border-bottom: 2px solid #2563eb; }
h2 { font-size: 14pt; margin: 18pt 0 6pt; padding-left: 6pt; border-left: 4px solid #2563eb; }
h3 { font-size: 12pt; margin: 14pt 0 4pt; }
p { margin: 5pt 0; }
ul, ol { margin: 4pt 0 8pt 18pt; padding: 0; }
li { margin: 2pt 0; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 9.5pt; }
th, td { border: 1px solid #cbd5e1; padding: 4pt 6pt; text-align: left; vertical-align: top; }
th { background: #eef2ff; font-weight: 600; }
tr:nth-child(even) td { background: #fafbfc; }
code { background: #f1f5f9; padding: 1px 4px; border-radius: 3px; font-size: 9.5pt;
       font-family: Consolas, "Courier New", monospace; }
pre { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8pt 10pt;
      overflow-x: auto; page-break-inside: avoid; }
pre code { background: none; padding: 0; }
blockquote { margin: 8pt 0; padding: 6pt 10pt; border-left: 3px solid #94a3b8;
             background: #f8fafc; color: #475569; }
blockquote p { margin: 2pt 0; }
hr { border: 0; border-top: 1px solid #e2e8f0; margin: 14pt 0; }
a { color: #1d4ed8; text-decoration: none; }
strong { font-weight: 600; }
h1, h2, h3 { page-break-after: avoid; }
table, pre, blockquote { page-break-inside: avoid; }
@media print { body { max-width: none; padding: 0; } }
"""

INLINE_CODE = re.compile(r"`([^`]+)`")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def inline(text: str) -> str:
    text = html.escape(text)
    text = INLINE_CODE.sub(lambda m: f"<code>{m.group(1)}</code>", text)
    text = BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", text)
    text = LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
    return text


def is_table_sep(line: str) -> bool:
    return bool(re.fullmatch(r"\s*\|?[\s:\-|]+\|[\s:\-|]*\s*", line)) and "-" in line


def split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def convert(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # 围栏代码块
        if stripped.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(buf)) + "</code></pre>")
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # 分隔线
        if re.fullmatch(r"-{3,}", stripped):
            out.append("<hr>")
            i += 1
            continue

        # 表格
        if stripped.startswith("|") and i + 1 < n and is_table_sep(lines[i + 1]):
            header = split_row(stripped)
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            parts = ["<table>", "<thead><tr>"]
            parts += [f"<th>{inline(c)}</th>" for c in header]
            parts.append("</tr></thead><tbody>")
            for row in rows:
                parts.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>")
            parts.append("</tbody></table>")
            out.append("".join(parts))
            continue

        # 引用
        if stripped.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            out.append("<blockquote><p>" + inline(" ".join(buf)) + "</p></blockquote>")
            continue

        # 无序列表
        if re.match(r"^[-*]\s+", stripped):
            items = []
            while i < n and re.match(r"^[-*]\s+", lines[i].strip()):
                items.append(re.sub(r"^[-*]\s+", "", lines[i].strip()))
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
            continue

        # 有序列表
        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < n and re.match(r"^\d+\.\s+", lines[i].strip()):
                items.append(re.sub(r"^\d+\.\s+", "", lines[i].strip()))
                i += 1
            out.append("<ol>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ol>")
            continue

        # 段落
        buf = []
        while i < n:
            s = lines[i].strip()
            if not s or s.startswith(("#", "|", ">", "```")) or re.match(r"^[-*]\s+", s) or re.match(r"^\d+\.\s+", s):
                break
            buf.append(s)
            i += 1
        out.append("<p>" + inline(" ".join(buf)) + "</p>")

    return "\n".join(out)


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: md2html.py <input.md> <output.html> [title]")
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    title = sys.argv[3] if len(sys.argv) > 3 else os.path.splitext(os.path.basename(src))[0]
    md = open(src, encoding="utf-8").read()
    body = convert(md)
    doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
{body}
</body>
</html>
"""
    os.makedirs(os.path.dirname(os.path.abspath(dst)) or ".", exist_ok=True)
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"html -> {dst} ({len(doc)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
