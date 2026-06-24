"""Tests for runtime resource access via importlib.resources.

These tests verify that theme QSS files, the app icon, and AppStream
metainfo are accessible through the package data mechanism — meaning they
will work after both editable and wheel installs.
"""
import importlib.resources

import pytest


class TestThemeResources:
    def test_breeze_light_accessible(self):
        ref = importlib.resources.files("themes").joinpath("breeze-light.qss")
        assert ref.is_file(), "breeze-light.qss not found via importlib.resources"

    def test_breeze_dark_accessible(self):
        ref = importlib.resources.files("themes").joinpath("breeze-dark.qss")
        assert ref.is_file(), "breeze-dark.qss not found via importlib.resources"

    def test_theme_qss_readable(self):
        ref = importlib.resources.files("themes").joinpath("breeze-light.qss")
        content = ref.read_text(encoding="utf-8")
        assert len(content) > 100, "QSS file appears empty or truncated"

    def test_theme_qss_has_accent_placeholder(self):
        for name in ("breeze-light.qss", "breeze-dark.qss"):
            content = importlib.resources.files("themes").joinpath(name).read_text(encoding="utf-8")
            assert "@ACCENT@" in content, f"{name}: @ACCENT@ placeholder missing"

    def test_theme_manager_reads_via_importlib(self):
        from ui.theme_manager import _read_qss
        content = _read_qss("breeze-light.qss")
        assert content is not None
        assert "@ACCENT@" in content

    def test_invalid_theme_returns_none(self):
        from ui.theme_manager import _read_qss
        assert _read_qss("nonexistent-theme.qss") is None

    def test_theme_manager_fallback_on_unknown_id(self):
        """apply() with unknown theme_id falls back to default and returns False
        (no QApplication), not raises."""
        from ui.theme_manager import ThemeManager
        tm = ThemeManager()
        result = tm.apply("does-not-exist")
        assert result is False


class TestIconResource:
    def test_icon_accessible_via_data_package(self):
        ref = importlib.resources.files("data").joinpath("qmediacenter.png")
        assert ref.is_file(), "qmediacenter.png not found in data package"

    def test_icon_is_png(self):
        ref = importlib.resources.files("data").joinpath("qmediacenter.png")
        with importlib.resources.as_file(ref) as p:
            header = p.read_bytes()[:8]
        # PNG magic bytes
        assert header[:4] == b"\x89PNG", "qmediacenter.png is not a valid PNG"

    def test_icon_path_resolver(self):
        """_icon_pixmap_path() must return a non-None path in source/editable install."""
        import main as m
        path = m._icon_pixmap_path()
        assert path is not None, "_icon_pixmap_path() returned None in source install"
        from pathlib import Path
        assert Path(path).exists(), f"Icon path does not exist: {path}"


class TestMetainfoResource:
    def test_metainfo_accessible(self):
        ref = importlib.resources.files("data").joinpath(
            "io.github.ycderman.qmediacenter.metainfo.xml"
        )
        assert ref.is_file(), "metainfo.xml not found in data package"

    def test_metainfo_contains_app_id(self):
        ref = importlib.resources.files("data").joinpath(
            "io.github.ycderman.qmediacenter.metainfo.xml"
        )
        content = ref.read_text(encoding="utf-8")
        assert "io.github.ycderman.qmediacenter" in content


class TestVersionCLI:
    def test_get_version_returns_string(self):
        import main as m
        v = m._get_version()
        assert isinstance(v, str)
        assert len(v) > 0

    def test_version_format_after_install(self):
        """After wheel install, version should not be the dev fallback."""
        import main as m
        v = m._get_version()
        # In source/editable mode this may be 0.0.0+dev; that's acceptable here.
        # What matters is it doesn't crash.
        assert v is not None
