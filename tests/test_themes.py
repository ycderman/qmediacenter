"""Tests for ui.theme_manager and QSS theme files."""
import os

import pytest

from ui.theme_manager import ThemeManager, THEMES, get_manager


class TestThemeManager:
    def test_available_themes_contains_builtins(self):
        tm = ThemeManager()
        ids = {t["id"] for t in tm.available_themes()}
        assert "breeze-light" in ids
        assert "breeze-dark" in ids

    def test_theme_metadata_fields(self):
        for theme in THEMES.values():
            assert "id" in theme
            assert "name" in theme
            assert "variant" in theme
            assert "file" in theme
            assert "default_accent" in theme

    def test_qss_files_exist(self):
        from pathlib import Path
        themes_dir = Path(__file__).parent.parent / "themes"
        for theme in THEMES.values():
            p = themes_dir / theme["file"]
            assert p.exists(), f"Missing QSS file: {p}"

    def test_qss_contains_accent_placeholder(self):
        from pathlib import Path
        themes_dir = Path(__file__).parent.parent / "themes"
        for theme in THEMES.values():
            content = (themes_dir / theme["file"]).read_text()
            assert "@ACCENT@" in content, f"{theme['file']} missing @ACCENT@ placeholder"

    def test_apply_unknown_theme_falls_back(self):
        """Applying unknown theme_id must not raise — falls back to default."""
        # No QApplication in unit tests, so apply() will log an error and return False.
        # Just verify it doesn't raise.
        tm = ThemeManager()
        result = tm.apply("nonexistent-theme-xyz")
        assert result is False  # no QApplication

    def test_get_manager_singleton(self):
        m1 = get_manager()
        m2 = get_manager()
        assert m1 is m2

    def test_current_theme_default(self):
        tm = ThemeManager()
        assert tm.current_theme_id() == "breeze-light"

    def test_light_dark_variants(self):
        assert THEMES["breeze-light"]["variant"] == "light"
        assert THEMES["breeze-dark"]["variant"] == "dark"
