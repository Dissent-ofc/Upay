"""
Bulk-download textbook PDFs from a URL list and drop them straight into the
Nivaran folder structure: data/raw_pdfs/<Board>/<Grade>/<Subject>/<name>.pdf

WHERE TO GET THE URLS:
NCERT's own site (ncert.nic.in) disallows automated crawling in its
robots.txt, so this script does not scrape it directly. Instead, use the
Internet Archive's verified NCERT mirror, which hosts the same official
PDFs and allows direct downloads:

  1. Go to https://archive.org/details/ncert-<bookcode> in your browser,
     where <bookcode> is NCERT's book code (e.g. "jesc1" = Class 10
     Science, "jemh1" = Class 10 Math, "iesc1" = Class 9 Science).
     Look up the code for your book at https://archive.org/details/ncert-books-class-1-to-12-2020
     (a master collection covering every class/subject) or by searching
     "archive.org ncert <class> <subject>".
  2. Click "SHOW ALL" / "Files for ncert-<bookcode>" to see the file
     listing — each chapter has its own <bookcode><NN>.pdf, e.g.
     jesc101.pdf, jesc102.pdf, ... jesc116.pdf.
  3. Copy each PDF's direct link (format:
     https://archive.org/download/ncert-<bookcode>/<bookcode><NN>.pdf)
     into a text file (see download_list.example.txt in this folder).
  4. Run this script to download them all and sort them automatically.

USAGE:
    python scripts/bulk_download.py download_list.txt

Where download_list.txt has one line per PDF, comma separated:
    <url>,<Board>,<Grade>,<Subject>,<chapter_filename_without_extension>

Example line:
    https://archive.org/download/ncert-jesc1/jesc101.pdf,CBSE,Class10,Science,ch01_chemical_reactions

Lines starting with # are treated as comments and skipped.
"""

import csv
import sys
import time
from pathlib import Path

import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_PDF_DIR = ROOT_DIR / "data" / "raw_pdfs"

# Be polite: a real browser User-Agent, and a small delay between requests
# so we're not hammering any server.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
DELAY_BETWEEN_DOWNLOADS_SECONDS = 1.5


def parse_download_list(list_path: Path):
    """
    Yields (url, board, grade, subject, chapter_name) for each valid line.
    Skips blank lines and lines starting with #.
    """
    with open(list_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for line_num, row in enumerate(reader, start=1):
            if not row or not row[0].strip() or row[0].strip().startswith("#"):
                continue
            if len(row) != 5:
                print(
                    f"  Line {line_num}: expected 5 comma-separated fields "
                    f"(url,board,grade,subject,chapter_name), got {len(row)} — skipping."
                )
                continue
            url, board, grade, subject, chapter_name = (x.strip() for x in row)
            yield url, board, grade, subject, chapter_name


def download_one(url: str, dest_path: Path) -> bool:
    """Download a single PDF to dest_path. Returns True on success."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        if not response.content.startswith(b"%PDF"):
            print(f"    Warning: response doesn't look like a PDF (got other content). Skipping.")
            return False
        dest_path.write_bytes(response.content)
        return True
    except requests.RequestException as e:
        print(f"    Failed: {e}")
        return False


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/bulk_download.py <download_list.txt>")
        sys.exit(1)

    list_path = Path(sys.argv[1])
    if not list_path.exists():
        print(f"File not found: {list_path}")
        sys.exit(1)

    entries = list(parse_download_list(list_path))
    if not entries:
        print("No valid entries found in the download list.")
        sys.exit(1)

    print(f"Found {len(entries)} PDFs to download.\n")

    succeeded, failed, skipped = 0, 0, 0

    for url, board, grade, subject, chapter_name in entries:
        dest_dir = RAW_PDF_DIR / board / grade / subject
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / f"{chapter_name}.pdf"

        if dest_path.exists():
            print(f"  Already exists, skipping: {board}/{grade}/{subject}/{chapter_name}.pdf")
            skipped += 1
            continue

        print(f"  Downloading {board}/{grade}/{subject}/{chapter_name}.pdf ...")
        if download_one(url, dest_path):
            print(f"    Saved.")
            succeeded += 1
        else:
            failed += 1

        time.sleep(DELAY_BETWEEN_DOWNLOADS_SECONDS)

    print(f"\nDone. Downloaded: {succeeded}, Failed: {failed}, Already had: {skipped}")
    if succeeded > 0:
        print("Next step: python -m src.ingest")


if __name__ == "__main__":
    main()
