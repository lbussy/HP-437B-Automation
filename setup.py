"""Stamp report identity into built artifacts; editable source uses live Git metadata."""

import tomllib
from pathlib import Path
from runpy import run_path

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

ROOT = Path(__file__).resolve().parent


def producer_snapshot():
    helper = run_path(str(ROOT / "src/hp437b/report_identity.py"))
    producer = helper["identify"]()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    if producer["version"] is not None and producer["version"] != version:
        producer["dirty"] = True
        helper["_release"](producer, producer["semantic_tags"])
    producer["version"] = version
    return helper, producer


class ReportBuild(build_py):
    def run(self):
        if self.editable_mode:
            return super().run()
        helper, producer = producer_snapshot()
        super().run()
        package = Path(self.build_lib) / "hp437b"
        if helper["_source_hashes"](package) != helper["_source_hashes"](ROOT / "src/hp437b"):
            producer["dirty"] = True
            helper["_release"](producer, producer["semantic_tags"])
        helper["write_build_stamp"](package, producer)

    def get_outputs(self, include_bytecode=True):
        outputs = super().get_outputs(include_bytecode)
        if not self.editable_mode:
            outputs.append(str(Path(self.build_lib) / "hp437b/_report_build.json"))
        return list(dict.fromkeys(outputs))


class ReportSdist(sdist):
    def make_release_tree(self, base_dir, files):
        # Snapshot before the temporary release tree can make a clean checkout look dirty.
        helper, producer = producer_snapshot()
        super().make_release_tree(base_dir, files)
        helper["write_build_stamp"](Path(base_dir) / "src/hp437b", producer)


setup(cmdclass={"build_py": ReportBuild, "sdist": ReportSdist})
