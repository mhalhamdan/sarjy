# /// script
# requires-python = ">=3.12"
# dependencies = ["markdown>=3.7"]
# ///
"""Render docs/USER_GUIDE.md to docs/Sarjy-User-Guide.pdf with headless Chrome.

Usage (from the repository root):  uv run scripts/build_guide.py
Set CHROME to the browser executable if it isn't found automatically.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "USER_GUIDE.md"
OUTPUT = ROOT / "docs" / "Sarjy-User-Guide.pdf"

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome",
    "chromium",
    "chromium-browser",
]

STYLE = """
@page {
  size: A4;
  margin: 18mm 18mm 20mm;
  @bottom-center { content: counter(page); font: 9pt system-ui, sans-serif; color: #5d6670; }
}
:root { --accent: #0f766e; --text: #16191d; --muted: #5d6670; --border: #e2e5e9; }
body {
  font: 10.5pt/1.55 "Segoe UI", system-ui, -apple-system, Roboto, sans-serif;
  color: var(--text);
  margin: 0;
}
h1 {
  font-size: 26pt;
  margin: 0 0 4mm;
  padding-bottom: 3mm;
  border-bottom: 3px solid var(--accent);
}
h2 {
  font-size: 15pt;
  color: var(--accent);
  margin: 8mm 0 2mm;
  break-after: avoid;
}
p, ul, ol, table { margin: 0 0 3mm; }
li { margin-bottom: 1mm; }
li > ul { margin-top: 1mm; }
strong { font-weight: 600; }
em { color: var(--muted); }
code {
  font: 9.5pt Consolas, "SFMono-Regular", monospace;
  background: #f1f3f5;
  padding: 0 1mm;
  border-radius: 3px;
}
img {
  display: block;
  max-width: 100%;
  margin: 2mm auto 4mm;
  border: 1px solid var(--border);
  border-radius: 6px;
  break-inside: avoid;
}
img[alt^="The passcode"] { max-width: 55%; }
table { width: 100%; border-collapse: collapse; font-size: 9.5pt; break-inside: avoid; }
th, td { text-align: left; vertical-align: top; padding: 1.6mm 2.4mm; border-bottom: 1px solid var(--border); }
th { background: #f1f3f5; font-weight: 600; }
td:first-child { width: 36%; }
"""


def find_chrome() -> str:
    candidates = [os.environ["CHROME"]] if os.environ.get("CHROME") else CHROME_CANDIDATES
    for candidate in candidates:
        path = candidate if Path(candidate).is_file() else shutil.which(candidate)
        if path:
            return path
    sys.exit("Chrome or Edge not found; set CHROME to the browser executable.")


def main() -> None:
    body = markdown.markdown(SOURCE.read_text(encoding="utf-8"), extensions=["tables", "sane_lists"])
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<base href="{SOURCE.parent.as_uri()}/">'
        f"<title>Sarjy user guide</title><style>{STYLE}</style></head>"
        f"<body>{body}</body></html>"
    )
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "guide.html"
        page.write_text(html, encoding="utf-8")
        subprocess.run(
            [
                find_chrome(),
                "--headless=new",
                f"--user-data-dir={Path(tmp) / 'profile'}",
                "--no-pdf-header-footer",
                "--allow-file-access-from-files",
                f"--print-to-pdf={OUTPUT}",
                page.as_uri(),
            ],
            check=True,
            capture_output=True,
        )
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
