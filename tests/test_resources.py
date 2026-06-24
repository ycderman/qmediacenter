"""Tests for runtime resource access via importlib.resources."""
import importlib.resources
from unittest.mock import MagicMock, patch

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
        """apply() with unknown theme_id falls back gracefully without raising."""
        from ui.theme_manager import ThemeManager
        tm = ThemeManager()
        # Must not raise; return value depends on whether QApplication is running
        tm.apply("does-not-exist")


class TestIconResource:
    def test_icon_bytes_readable(self):
        """PNG bytes must be readable directly — no temp file involved."""
        ref = importlib.resources.files("data").joinpath("qmediacenter.png")
        png_bytes = ref.read_bytes()
        assert png_bytes[:4] == b"\x89PNG", "qmediacenter.png is not a valid PNG"
        assert len(png_bytes) > 1000, "PNG file suspiciously small"

    def test_icon_accessible_via_data_package(self):
        ref = importlib.resources.files("data").joinpath("qmediacenter.png")
        assert ref.is_file(), "qmediacenter.png not found in data package"

    def test_app_icon_with_qapplication(self, qtbot):
        """_app_icon() returns a non-null QIcon when a QApplication is running."""
        import main as m
        icon = m._app_icon()
        from PySide6.QtGui import QIcon
        assert isinstance(icon, QIcon)
        assert not icon.isNull()

    def test_app_icon_resource_unavailable_uses_fallback(self, qtbot):
        """When importlib.resources raises, _app_icon() falls back to the
        repo-relative path without crashing."""
        import main as m
        from PySide6.QtGui import QIcon

        # Patch importlib.resources.files inside the main module so read_bytes raises
        bad_ref = MagicMock()
        bad_ref.read_bytes.side_effect = FileNotFoundError("simulated missing resource")
        bad_pkg = MagicMock()
        bad_pkg.joinpath.return_value = bad_ref

        with patch("main.importlib.resources.files", return_value=bad_pkg):
            icon = m._app_icon()
            assert isinstance(icon, QIcon)
            # The repo-relative data/qmediacenter.png exists, so icon must not be null
            assert not icon.isNull()

    def test_app_icon_theme_fallback_no_crash(self, qtbot):
        """When both resource and file-system paths are unavailable,
        _app_icon() must return fromTheme without crashing."""
        import main as m
        from PySide6.QtGui import QIcon, QPixmap

        bad_bytes = b"not a png"

        def _bad_load(data, fmt=None):
            return False

        # Simulate importlib returning bad bytes and no on-disk file
        with patch("importlib.resources.files") as mock_files:
            mock_ref = MagicMock()
            mock_ref.read_bytes.return_value = bad_bytes
            mock_files.return_value.joinpath.return_value = mock_ref

            with patch("os.path.exists", return_value=False):
                with patch.object(QPixmap, "loadFromData", return_value=False):
                    icon = m._app_icon()
                    assert isinstance(icon, QIcon)


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

    def test_version_non_empty(self):
        import main as m
        v = m._get_version()
        assert v is not None
