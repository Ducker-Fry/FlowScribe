"""Theme management for FlowScribe GUI.

Provides functions to load and apply QSS themes to the application.
"""

from __future__ import annotations

from pathlib import Path

from flowscribe.utils.runtime_layout import resolve_runtime_layout


def _theme_dir() -> Path:
    layout = resolve_runtime_layout()
    candidates = (
        layout.code_dir / "flowscribe" / "gui" / "themes",
        layout.app_root / "flowscribe" / "gui" / "themes",
        Path(__file__).parent / "themes",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path(__file__).parent / "themes"


def get_available_themes() -> tuple[str, ...]:
    """Return tuple of available theme names."""
    return ("light", "dark")


def get_current_theme(app) -> str:
    """Get the current theme name from the application.

    Args:
        app: QApplication instance

    Returns:
        Current theme name ("light" or "dark"), defaults to "light"
    """
    if app is None:
        return "light"
    theme = app.property("current_theme")
    return theme if theme in get_available_themes() else "light"


def load_theme_stylesheet(theme_name: str) -> str:
    """Load QSS stylesheet content for the specified theme.

    Args:
        theme_name: Name of the theme ("light" or "dark")

    Returns:
        QSS stylesheet content as string

    Raises:
        ValueError: If theme_name is not a valid theme
        FileNotFoundError: If theme file does not exist
    """
    if theme_name not in get_available_themes():
        raise ValueError(
            f"Invalid theme '{theme_name}'. Available themes: {get_available_themes()}"
        )

    theme_file = _theme_dir() / f"{theme_name}.qss"
    if not theme_file.exists():
        raise FileNotFoundError(f"Theme file not found: {theme_file}")

    return theme_file.read_text(encoding="utf-8")


def apply_theme(app, theme_name: str) -> None:
    """Apply the specified theme to the QApplication.

    Args:
        app: QApplication instance
        theme_name: Name of the theme to apply ("light" or "dark")

    Raises:
        ValueError: If theme_name is not a valid theme
        FileNotFoundError: If theme file does not exist
    """
    stylesheet = load_theme_stylesheet(theme_name)
    app.setStyleSheet(stylesheet)

    # Apply arrow icons to all combo boxes and spin boxes
    _apply_arrow_icons(app, theme_name)

    # Store current theme in app property for icon updates
    app.setProperty("current_theme", theme_name)


def _apply_arrow_icons(app, theme_name: str) -> None:
    """Apply arrow icons to combo boxes and spin boxes.

    This is a workaround for QSS arrow rendering issues.
    """
    try:
        from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QSpinBox

        from flowscribe.gui.arrow_icons import (
            get_combo_arrow_icon,
            get_spin_down_arrow_icon,
            get_spin_up_arrow_icon,
        )

        combo_icon = get_combo_arrow_icon(theme_name)
        spin_up_icon = get_spin_up_arrow_icon(theme_name)
        spin_down_icon = get_spin_down_arrow_icon(theme_name)

        # Apply to all existing widgets
        for widget in app.allWidgets():
            if isinstance(widget, QComboBox):
                # Store icons as widget property to prevent garbage collection
                widget.setProperty("_arrow_icon", combo_icon)
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setProperty("_up_arrow_icon", spin_up_icon)
                widget.setProperty("_down_arrow_icon", spin_down_icon)
    except Exception:
        # Silently fail if icons cannot be applied
        pass

