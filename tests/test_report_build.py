"""Real tagged sdist → wheel → installed report identity, in disposable repositories."""

import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
IDENTITY = "import sys,json;sys.path.insert(0,sys.argv[1]);from hp437b.report_identity import identify;from hp437b.report_sheet import producer_note;i=identify();print(json.dumps({'identity':i,'note':producer_note(i)}))"


def command(args, cwd):
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout[-2500:] + result.stderr[-2500:]
    return result.stdout.strip()


def git(root, *args):
    return command(
        ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", *args], root
    )


@pytest.fixture(scope="module")
def tagged_packages(tmp_path_factory):
    if shutil.which("git") is None:
        pytest.skip("Git is needed for the isolated release-build check")
    base = tmp_path_factory.mktemp("release-build")
    root = base / "source"
    (root / "src/hp437b").mkdir(parents=True)
    for name in (
        "pyproject.toml",
        "setup.py",
        "MANIFEST.in",
        "README.md",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "requirements-dev.lock",
        ".gitignore",
    ):
        shutil.copy2(ROOT / name, root / name)
    for source in (ROOT / "src/hp437b").glob("*.py"):
        shutil.copy2(source, root / "src/hp437b" / source.name)
    git(root, "init", "--quiet")
    git(root, "config", "user.name", "Build Test")
    git(root, "config", "user.email", "build-test@example.invalid")
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "Fictional release fixture")
    commit = git(root, "rev-parse", "HEAD")
    git(root, "tag", "-a", "v1.2.3", "-m", "Fictional test tag")
    artifacts = base / "artifacts"
    command([sys.executable, "-m", "build", "--no-isolation", "--outdir", str(artifacts)], root)
    assert git(root, "status", "--porcelain") == ""
    assert not (root / "src/hp437b/_report_build.json").exists()
    return {
        "root": root,
        "wheel": next(artifacts.glob("*.whl")),
        "sdist": next(artifacts.glob("*.tar.gz")),
        "commit": commit,
    }


def installed(tagged, output):
    with zipfile.ZipFile(tagged["wheel"]) as wheel:
        # This is the wheel just produced from inspected project code, not an input bundle.
        wheel.extractall(output)
        assert "hp437b/_report_build.json" in wheel.namelist()


def identity(package_root, cwd):
    return json.loads(command([sys.executable, "-c", IDENTITY, str(package_root)], cwd))


def test_tagged_release_survives_sdist_wheel_and_foreign_git_cwd(tagged_packages, tmp_path):
    package = tmp_path / "installed"
    installed(tagged_packages, package)
    foreign = tmp_path / "unrelated-repo"
    foreign.mkdir()
    git(foreign, "init", "--quiet")
    output = identity(package, foreign)
    producer = output["identity"]
    assert output["note"] == "Report Harness: HP 437B Automation v1.2.3"
    assert producer["commit"] == tagged_packages["commit"]
    assert producer["dirty"] is False and producer["basis"] == "build_metadata"
    assert producer["release_tag"] == "v1.2.3"


def test_modified_installed_release_falls_back_to_commit(tagged_packages, tmp_path):
    package = tmp_path / "installed"
    installed(tagged_packages, package)
    source = package / "hp437b/protocol.py"
    source.write_bytes(source.read_bytes() + b"\n# local modification\n")
    output = identity(package, tmp_path)
    assert output["identity"]["release_version"] is None
    assert output["identity"]["commit"] == tagged_packages["commit"]
    assert f"commit {tagged_packages['commit'][:12]}" in output["note"]
    assert "modified working tree" in output["note"]


def test_dirty_tagged_checkout_is_development(tagged_packages, tmp_path):
    root = tmp_path / "source"
    shutil.copytree(tagged_packages["root"], root)
    (root / "uncommitted.txt").write_text("development change")
    output = identity(root / "src", root)
    assert output["identity"]["release_version"] is None
    assert output["identity"]["commit"] == tagged_packages["commit"]
    assert "modified working tree" in output["note"]


def test_clean_commit_after_tag_is_development(tagged_packages, tmp_path):
    root = tmp_path / "source"
    shutil.copytree(tagged_packages["root"], root)
    (root / "development.txt").write_text("next development commit")
    git(root, "add", "development.txt")
    git(root, "commit", "--quiet", "-m", "Fictional development commit")
    commit = git(root, "rev-parse", "HEAD")
    output = identity(root / "src", root)
    assert output["identity"]["release_version"] is None
    assert output["identity"]["commit"] == commit and commit != tagged_packages["commit"]
    assert output["note"] == f"Report Harness: HP 437B Automation commit {commit[:12]}"


def test_lightweight_semantic_tag_is_supported(tagged_packages, tmp_path):
    root = tmp_path / "source"
    shutil.copytree(tagged_packages["root"], root)
    git(root, "tag", "-d", "v1.2.3")
    git(root, "tag", "1.2.3")
    output = identity(root / "src", root)
    assert output["identity"]["release_tag"] == "1.2.3"
    assert output["note"] == "Report Harness: HP 437B Automation v1.2.3"
