"""Check repository Markdown links, inventory IDs, and reference manifests."""

import hashlib
import re
from pathlib import Path
from urllib.parse import unquote


def main():
    root = Path(__file__).resolve().parents[1]
    for path in [root / "README.md", *root.glob("docs/**/*.md")]:
        source = path.read_text()
        for target in re.findall(r"\]\(([^)]+)\)", source):
            if "://" in target or target.startswith("mailto:"):
                continue
            name, _, anchor = target.partition("#")
            destination = path.parent / unquote(name) if name else path
            assert destination.exists(), (path, target)
            if anchor and destination.suffix == ".md":
                headings = re.findall(r"^#+\s+(.+)$", destination.read_text(), re.M)
                anchors = [re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-") for h in headings]
                assert anchor in anchors, (path, target)
        for number, line in enumerate(source.splitlines(), 1):
            assert line == line.rstrip(), (path, number, "trailing whitespace")
            if line.startswith("|"):
                assert line.endswith("|"), (path, number, "table boundary")
    matrix = (root / "docs/inventory/COVERAGE.md").read_text()
    ledger = (root / "docs/validation/OFFLINE-PARAMETER-COVERAGE.md").read_text()
    for prefix, count in [("C", 118), ("G", 20)]:
        for source in (matrix, ledger):
            ids = re.findall(r"^\| \[(" + prefix + r"\d{3})\b", source, re.M)
            assert len(ids) == len(set(ids)) == count
    verified = 0
    for manifest in root.glob("output/pdf/**/SHA256SUMS.txt"):
        for line in manifest.read_text().splitlines():
            expected, name = line.split(maxsplit=1)
            assert hashlib.sha256((manifest.parent / name).read_bytes()).hexdigest() == expected
            verified += 1
    print(
        f"Markdown links/anchors/tables, 138 IDs in matrix/ledger, {verified} PDF checksums passed"
    )


if __name__ == "__main__":
    main()
