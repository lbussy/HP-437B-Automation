"""Identify the report producer independently of captured measurement software.

Never search the caller's cwd or an input bundle for Git metadata. Installed
packages without recorded VCS metadata retain an explicitly unknown commit.
"""

import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import tomllib
from pathlib import Path
from tempfile import NamedTemporaryFile

PACKAGE = "hp437b-automation"
PROJECT = "HP 437B Automation"


def _commit(value):
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value)
        else None
    )


def _checkout():
    module = Path(__file__).resolve()
    root = module.parents[2]
    if module != root / "src/hp437b/report_identity.py" or not (root / ".git").exists():
        return None, None
    try:
        project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
        if project["name"] == PACKAGE:
            return root, project.get("version")
    except (OSError, KeyError, ValueError, TypeError):
        pass
    return None, None


def _git(root, *args):
    # Inherited Git routing variables must not redirect this query to another repo.
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    result = subprocess.run(
        ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(root), *args],
        env=environment,
        capture_output=True,
        text=True,
        timeout=2,
        check=True,
    )
    return result.stdout.strip()


STAMP = "_report_build.json"
SEMVER = re.compile(
    r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)


def semantic_version(tag):
    if not isinstance(tag, str) or len(tag) > 128:
        return None
    match = SEMVER.fullmatch(tag)
    if match is None:
        return None
    prerelease = match.group(4)
    if prerelease and any(
        part.isdigit() and len(part) > 1 and part.startswith("0") for part in prerelease.split(".")
    ):
        return None
    return tag.removeprefix("v")


def _release(result, tags):
    result["semantic_tags"] = sorted({tag for tag in tags if semantic_version(tag) is not None})
    result.update(release_version=None, release_tag=None)
    versions = {semantic_version(tag) for tag in result["semantic_tags"]}
    if result.get("commit") and result.get("dirty") is False and len(versions) == 1:
        version = versions.pop()
        result.update(
            release_version=version,
            release_tag=(
                "v" + version
                if "v" + version in result["semantic_tags"]
                else result["semantic_tags"][0]
            ),
        )
    return result


def _source_hashes(package):
    files = sorted(Path(package).rglob("*.py"))
    if not files or len(files) > 128:
        raise ValueError("Invalid package source inventory")
    hashes = {}
    total = 0
    for path in files:
        if path.is_symlink() or path.stat().st_size > 1024 * 1024:
            raise ValueError("Invalid package source file")
        data = path.read_bytes()
        total += len(data)
        if total > 4 * 1024 * 1024:
            raise ValueError("Package source inventory too large")
        hashes[path.relative_to(package).as_posix()] = hashlib.sha256(data).hexdigest()
    return hashes


def write_build_stamp(package, producer):
    """Called only by build hooks, into the wheel/sdist staging tree."""
    package = Path(package)
    data = {
        "schema": "hp437b.report-build.v1",
        "producer": producer,
        "source_hashes": _source_hashes(package),
    }
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=package, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, sort_keys=True, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, package / STAMP)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _build_identity():
    package = Path(__file__).resolve().parent
    stamp = package / STAMP
    try:
        if not stamp.is_file() or stamp.is_symlink() or stamp.stat().st_size > 32768:
            return None
        data = json.loads(stamp.read_bytes())
        producer = data["producer"]
        if data["schema"] != "hp437b.report-build.v1" or producer["project"] != PROJECT:
            return None
        if producer["commit"] is not None and _commit(producer["commit"]) is None:
            return None
        if type(producer["dirty"]) not in (bool, type(None)):
            return None
        if producer["version"] is not None and not isinstance(producer["version"], str):
            return None
        tags = producer.get("semantic_tags", [])
        if not isinstance(tags, list) or not all(semantic_version(tag) is not None for tag in tags):
            return None
        result = {key: producer[key] for key in ("project", "version", "commit", "dirty")}
        result["basis"] = "build_metadata"
        if _source_hashes(package) != data["source_hashes"]:
            result["dirty"] = True
        return _release(result, tags)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def identify():
    """Version/full commit/dirty state of this producer, with honest fallbacks."""
    result = {
        "project": PROJECT,
        "version": None,
        "commit": None,
        "dirty": None,
        "basis": "unavailable",
        "semantic_tags": [],
        "release_version": None,
        "release_tag": None,
    }
    distribution = None
    try:
        distribution = importlib.metadata.distribution(PACKAGE)
        result.update(version=distribution.version, basis="installed_metadata")
    except importlib.metadata.PackageNotFoundError:
        pass
    root, source_version = _checkout()
    if root is not None:
        result.update(version=source_version or result["version"], basis="source_checkout")
        try:
            result["commit"] = _commit(_git(root, "rev-parse", "HEAD"))
            result["dirty"] = bool(_git(root, "status", "--porcelain", "--untracked-files=normal"))
            if result["commit"]:
                tags = _git(root, "tag", "--points-at", result["commit"]).splitlines()
                _release(result, tags)
                if _commit(_git(root, "rev-parse", "HEAD")) != result["commit"]:
                    result["dirty"] = None
                    _release(result, tags)
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        built = _build_identity()
        if built is not None:
            if distribution is not None and built["version"] != distribution.version:
                built.update(version=distribution.version, dirty=True)
                _release(built, built["semantic_tags"])
            return built
    if root is None and distribution is not None:
        try:
            metadata = json.loads(distribution.read_text("direct_url.json") or "null")
            vcs = metadata.get("vcs_info", {}) if isinstance(metadata, dict) else {}
            if vcs.get("vcs") == "git" and _commit(vcs.get("commit_id")):
                result.update(commit=vcs["commit_id"], basis="installed_vcs_metadata")
        except (ValueError, TypeError, OSError):
            pass
    return result
