"""Report producer identity must never adopt the measurement/caller repository."""

import json
import subprocess
from types import SimpleNamespace

import pytest

from hp437b import report_identity as i
from hp437b import report_sheet


def distribution(version="0.1.0", metadata=None):
    return SimpleNamespace(version=version, read_text=lambda name: metadata)


@pytest.mark.parametrize(
    "status,dirty", [("", False), (" M src/changed.py", True), ("?? src/new.py", True)]
)
def test_source_checkout_version_commit_and_modification_state(
    tmp_path, monkeypatch, status, dirty
):
    root = tmp_path / "checkout"
    (root / ".git").mkdir(parents=True)
    (root / "src/hp437b").mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\nname="hp437b-automation"\nversion="0.2.0"\n')
    monkeypatch.setattr(i, "__file__", str(root / "src/hp437b/report_identity.py"))
    monkeypatch.setattr(i.importlib.metadata, "distribution", lambda name: distribution())
    monkeypatch.setattr(
        i, "_git", lambda path, *args: "a" * 40 if args[0] == "rev-parse" else status
    )
    result = i.identify()
    assert result["version"] == "0.2.0" and result["commit"] == "a" * 40
    assert result["dirty"] is dirty and result["basis"] == "source_checkout"
    assert ("modified working tree" in report_sheet.producer_note(result)) is dirty


def test_wheel_in_foreign_cwd_never_claims_that_git_commit(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="hp437b-automation"\nversion="99.0"\n'
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(i, "__file__", str(tmp_path / "site-packages/hp437b/report_identity.py"))
    monkeypatch.setattr(i.importlib.metadata, "distribution", lambda name: distribution())
    monkeypatch.setattr(i, "_git", lambda *args: pytest.fail("must not query caller Git"))
    result = i.identify()
    assert result["commit"] is None and result["version"] == "0.1.0"
    assert "commit unavailable" in report_sheet.producer_note(result)


def test_recorded_vcs_install_commit_is_used_without_retaining_origin_url(monkeypatch):
    metadata = json.dumps(
        {
            "url": "https://private-user:secret@example.invalid/repo",
            "vcs_info": {"vcs": "git", "commit_id": "c" * 40},
        }
    )
    monkeypatch.setattr(i, "_checkout", lambda: (None, None))
    monkeypatch.setattr(
        i.importlib.metadata, "distribution", lambda name: distribution(metadata=metadata)
    )
    result = i.identify()
    assert result["commit"] == "c" * 40 and result["basis"] == "installed_vcs_metadata"
    assert "secret" not in str(result) and "example.invalid" not in str(result)


@pytest.mark.parametrize(
    "metadata", ['{"vcs_info":{"vcs":"git","commit_id":"not-a-commit"}}', "broken-json"]
)
def test_bad_vcs_metadata_retains_unknown_commit(monkeypatch, metadata):
    monkeypatch.setattr(i, "_checkout", lambda: (None, None))
    monkeypatch.setattr(
        i.importlib.metadata, "distribution", lambda name: distribution(metadata=metadata)
    )
    assert i.identify()["commit"] is None


def test_git_unavailable_preserves_version_and_unknown_commit(tmp_path, monkeypatch):
    monkeypatch.setattr(i, "_checkout", lambda: (tmp_path, "0.3.0"))
    monkeypatch.setattr(i.importlib.metadata, "distribution", lambda name: distribution())

    def missing(*args):
        raise FileNotFoundError("git unavailable")

    monkeypatch.setattr(i, "_git", missing)
    result = i.identify()
    assert result["version"] == "0.3.0" and result["commit"] is None and result["dirty"] is None


def test_failed_status_does_not_claim_clean_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(i, "_checkout", lambda: (tmp_path, "0.1.0"))
    monkeypatch.setattr(i.importlib.metadata, "distribution", lambda name: distribution())

    def git(path, *args):
        if args[0] == "rev-parse":
            return "d" * 40
        raise subprocess.TimeoutExpired("git", 2)

    monkeypatch.setattr(i, "_git", git)
    result = i.identify()
    assert result["commit"] == "d" * 40 and result["dirty"] is None
    assert "working-tree state unknown" in report_sheet.producer_note(result)


def test_git_query_is_bounded_and_cannot_be_redirected_by_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "other"))
    seen = []

    def run(args, **kwargs):
        seen.append((args, kwargs))
        return SimpleNamespace(stdout="e" * 40 + "\n")

    monkeypatch.setattr(i.subprocess, "run", run)
    assert i._git(tmp_path, "rev-parse", "HEAD") == "e" * 40
    args, options = seen[0]
    assert args[:6] == [
        "git",
        "--no-optional-locks",
        "-c",
        "core.fsmonitor=false",
        "-C",
        str(tmp_path),
    ]
    assert options["timeout"] == 2 and options["check"] is True
    assert "GIT_DIR" not in options["env"] and not options.get("shell", False)


@pytest.mark.parametrize(
    "tag,expected",
    [
        ("v1.2.3", "1.2.3"),
        ("1.2.3", "1.2.3"),
        ("v0.0.0", "0.0.0"),
        ("v2.0.0-rc.1+build.02", "2.0.0-rc.1+build.02"),
        ("v01.2.3", None),
        ("v1.2", None),
        ("release/v1.2.3", None),
        ("v1.2.3-rc.01", None),
        ("v1.2.3+", None),
    ],
)
def test_strict_semantic_version_tags(tag, expected):
    assert i.semantic_version(tag) == expected


@pytest.mark.parametrize(
    "dirty,tags,release",
    [
        (False, ["v1.2.3"], "1.2.3"),
        (False, ["1.2.3", "v1.2.3"], "1.2.3"),
        (True, ["v1.2.3"], None),
        (None, ["v1.2.3"], None),
        (False, [], None),
        (False, ["not-a-release"], None),
        (False, ["v1.2.3", "v2.0.0"], None),
    ],
)
def test_release_label_only_for_unambiguous_clean_exact_tag(dirty, tags, release):
    result = i._release({"commit": "a" * 40, "dirty": dirty, "basis": "source_checkout"}, tags)
    assert result["release_version"] == release
    note = report_sheet.producer_note(result)
    if release:
        assert note == "Report Harness: HP 437B Automation v1.2.3"
        assert "commit" not in note
    else:
        assert "commit aaaaaaaaaaaa" in note and "v1.2.3" not in note
    assert result["commit"] == "a" * 40


def test_build_stamp_retains_release_without_git_and_detects_modified_sources(
    tmp_path, monkeypatch
):
    package = tmp_path / "installed/hp437b"
    package.mkdir(parents=True)
    source = package / "report_identity.py"
    source.write_text("# fictional installed module\n")
    producer = i._release(
        {
            "project": i.PROJECT,
            "version": "0.1.0",
            "commit": "b" * 40,
            "dirty": False,
            "basis": "source_checkout",
        },
        ["v1.2.3"],
    )
    i.write_build_stamp(package, producer)
    monkeypatch.setattr(i, "__file__", str(source))
    monkeypatch.setattr(i.importlib.metadata, "distribution", lambda name: distribution())
    monkeypatch.setattr(i, "_git", lambda *a: pytest.fail("installed stamp must not query Git"))
    result = i.identify()
    assert result["basis"] == "build_metadata" and result["release_version"] == "1.2.3"
    assert result["commit"] == "b" * 40
    source.write_text("# modified installed module\n")
    result = i.identify()
    assert result["dirty"] is True and result["release_version"] is None
    assert "modified working tree" in report_sheet.producer_note(result)


def test_moving_head_during_identity_query_never_claims_a_release(tmp_path, monkeypatch):
    monkeypatch.setattr(i, "_checkout", lambda: (tmp_path, "0.1.0"))
    monkeypatch.setattr(i.importlib.metadata, "distribution", lambda name: distribution())
    heads = iter(["a" * 40, "b" * 40])

    def git(path, *args):
        return next(heads) if args[0] == "rev-parse" else "v1.2.3" if args[0] == "tag" else ""

    monkeypatch.setattr(i, "_git", git)
    result = i.identify()
    assert result["release_version"] is None and result["dirty"] is None
    assert result["commit"] == "a" * 40
