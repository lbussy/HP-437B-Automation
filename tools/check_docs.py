"""Check repository Markdown links, inventory IDs, and reference manifests."""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote


def check_references(root):
    """Verify original bytes and resolve preserved manifests at relocated paths."""
    index = json.loads((root / "references/relocation-index.json").read_text())
    relocated = {item["previous_path"]: item for item in index["files"]}
    previous = {item["path"]: item["previous_path"] for item in index["files"]}
    assert len(relocated) == len(previous) == len(index["files"]), "Duplicate relocation entry"
    for item in index["files"]:
        data = (root / item["path"]).read_bytes()
        assert len(data) == item["bytes"], item["path"]
        assert hashlib.sha256(data).hexdigest() == item["sha256"], item["path"]
    verified = 0
    for manifest in root.glob("references/**/SHA256SUMS.txt"):
        for line in manifest.read_text().splitlines():
            expected, name = line.split(maxsplit=1)
            target = manifest.parent / name
            if not target.exists():
                original = root / previous[manifest.relative_to(root).as_posix()]
                old_target = (original.parent / name).resolve().relative_to(root).as_posix()
                target = root / relocated[old_target]["path"]
            assert hashlib.sha256(target.read_bytes()).hexdigest() == expected, (manifest, name)
            verified += 1
    for item in index.get("removed_files", []):
        assert not (root / item["path"]).exists(), item["path"]
        assert re.fullmatch(r"[0-9a-f]{64}", item["sha256"]), item["path"]
    return len(index["files"]), verified


def main():
    root = Path(__file__).resolve().parents[1]
    for path in [
        root / "README.md",
        root / "AGENTS.md",
        root / "CONTRIBUTING.md",
        root / "THIRD_PARTY_NOTICES.md",
        *root.glob("docs/**/*.md"),
        *root.glob("references/**/*.md"),
    ]:
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
    originals, verified = check_references(root)
    print(
        f"Markdown links/anchors/tables, 138 IDs in matrix/ledger, "
        f"{originals} preserved reference files, {verified} PDF checksum entries passed"
    )


if __name__ == "__main__":
    main()
