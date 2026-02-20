#!/usr/bin/env python3
from __future__ import annotations

import os
import pathlib
import shutil
import stat
import subprocess
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE_SRC_DIR = REPO_ROOT / "src"
INSTALLER_SOURCE = REPO_ROOT / "install_palisades_parking_cron.sh"


def make_executable(path: pathlib.Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR)


def write_file(path: pathlib.Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    make_executable(path)


class InstallerScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tempdir.name)
        self.project_dir = self.root / "project"
        self.src_dir = self.project_dir / "src"
        self.fake_bin_dir = self.root / "fake-bin"
        self.store_file = self.root / "crontab_store.txt"

        self.src_dir.mkdir(parents=True)
        self.fake_bin_dir.mkdir(parents=True)

        shutil.copy2(INSTALLER_SOURCE, self.project_dir / "install_palisades_parking_cron.sh")
        shutil.copy2(SOURCE_SRC_DIR / "palisades_parking_watch.py", self.src_dir / "palisades_parking_watch.py")

        self.installer = self.project_dir / "install_palisades_parking_cron.sh"
        make_executable(self.installer)

        fake_crontab = self.fake_bin_dir / "crontab"
        write_file(
            fake_crontab,
            """#!/usr/bin/env bash
set -euo pipefail
store="${FAKE_CRONTAB_STORE:?missing FAKE_CRONTAB_STORE}"
if [[ "${1:-}" == "-l" ]]; then
  if [[ -f "$store" ]]; then
    cat "$store"
    exit 0
  fi
  exit 1
fi
if [[ $# -eq 1 ]]; then
  cp "$1" "$store"
  exit 0
fi
exit 2
""",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_installer(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PATH"] = f"{self.fake_bin_dir}:{env.get('PATH', '')}"
        env["FAKE_CRONTAB_STORE"] = str(self.store_file)
        return subprocess.run(
            ["bash", str(self.installer), *args],
            text=True,
            capture_output=True,
            env=env,
            cwd=self.project_dir,
            check=False,
        )

    def test_rejects_interval_seconds_option(self) -> None:
        result = self.run_installer(
            "--target-date",
            "2026-02-28",
            "--interval-seconds",
            "30",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Unknown argument: --interval-seconds", result.stdout)

    def test_replaces_existing_marker_lines(self) -> None:
        self.store_file.write_text(
            "keep this line\n"
            "remove old # palisades-parking-watch\n"
            "remove legacy # alpine-parking-watch\n",
            encoding="utf-8",
        )

        result = self.run_installer(
            "--target-date",
            "2026-02-28",
            "--location",
            "PALISADES",
            "--interval-minutes",
            "5",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        updated = self.store_file.read_text(encoding="utf-8")
        self.assertIn("keep this line", updated)
        self.assertNotIn("# alpine-parking-watch", updated)
        self.assertEqual(updated.count("# palisades-parking-watch"), 1)
        self.assertIn("*/5 * * * *", updated)
        self.assertIn("palisades_parking_watch.py", updated)
        self.assertIn("--location 'PALISADES'", updated)

    def test_rejects_interval_minutes_above_59(self) -> None:
        result = self.run_installer(
            "--target-date",
            "2026-02-28",
            "--interval-minutes",
            "60",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--interval-minutes must be between 1 and 59", result.stdout)


if __name__ == "__main__":
    unittest.main()
