"""Tests for AppStream metainfo, desktop file, and project metadata."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


class TestDesktopFile:
    DESKTOP = ROOT / "packaging" / "qmediacenter.desktop"

    def test_desktop_file_exists(self):
        assert self.DESKTOP.exists()

    def test_desktop_file_has_required_keys(self):
        content = self.DESKTOP.read_text()
        for key in ("Name=", "Exec=", "Icon=", "Type=", "Categories="):
            assert key in content, f"Missing {key} in desktop file"

    def test_desktop_icon_matches_app_id(self):
        content = self.DESKTOP.read_text()
        assert "Icon=io.github.ycderman.qmediacenter" in content

    @pytest.mark.skipif(
        not Path("/usr/bin/desktop-file-validate").exists() and
        not Path("/usr/local/bin/desktop-file-validate").exists(),
        reason="desktop-file-validate not installed"
    )
    def test_desktop_file_validates(self):
        result = subprocess.run(
            ["desktop-file-validate", str(self.DESKTOP)],
            capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr


class TestAppStream:
    METAINFO = ROOT / "data" / "io.github.ycderman.qmediacenter.metainfo.xml"

    def test_metainfo_exists(self):
        assert self.METAINFO.exists()

    def test_metainfo_has_app_id(self):
        content = self.METAINFO.read_text()
        assert "io.github.ycderman.qmediacenter" in content

    def test_metainfo_has_required_tags(self):
        content = self.METAINFO.read_text()
        for tag in ("<name>", "<summary>", "<description>", "<url", "<releases"):
            assert tag in content, f"Missing {tag} in metainfo"

    @pytest.mark.skipif(
        subprocess.run(["sh", "-c", "command -v appstreamcli"], capture_output=True).returncode != 0,
        reason="appstreamcli not installed"
    )
    def test_appstream_validates(self):
        result = subprocess.run(
            ["appstreamcli", "validate", "--no-net", str(self.METAINFO)],
            capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr + result.stdout


class TestProjectMetadata:
    def test_pyproject_exists(self):
        assert (ROOT / "pyproject.toml").exists()

    def test_pyproject_has_name(self):
        content = (ROOT / "pyproject.toml").read_text()
        assert 'name = "qmediacenter"' in content

    def test_pyproject_has_entry_point(self):
        content = (ROOT / "pyproject.toml").read_text()
        assert "qmediacenter" in content and "main:main" in content

    def test_icon_exists(self):
        assert (ROOT / "data" / "qmediacenter.png").exists()

    def test_license_exists(self):
        assert (ROOT / "LICENSE").exists()

    def test_changelog_exists(self):
        assert (ROOT / "CHANGELOG.md").exists(), "CHANGELOG.md missing — create it"
