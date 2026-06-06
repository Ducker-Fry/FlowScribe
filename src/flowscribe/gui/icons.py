"""Icon management for FlowScribe GUI.

Provides SVG-based icons with theme support (light/dark mode).
Icons are based on Material Design Icons (Apache 2.0 license).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtSvg import QSvgRenderer


def _get_icon_path() -> Path:
    """Get the path to the icons directory.

    Handles both development (running from source) and production (PyInstaller bundle).
    """
    if getattr(sys, "frozen", False):
        # Running in PyInstaller bundle
        base_path = Path(sys._MEIPASS)  # type: ignore
        return base_path / "icons"
    else:
        # Running from source
        return Path(__file__).parent.parent.parent.parent / "icons"


# Path to application icon
_APP_ICON_PATH = _get_icon_path() / "flowscribe.png"


# Material Design Icons SVG paths (simplified, single color)
# Source: https://pictogrammers.com/library/mdi/ (Apache 2.0 license)
_ICON_PATHS = {
    "play": "M8,5.14V19.14L19,12.14L8,5.14Z",
    "stop": "M18,18H6V6H18V18Z",
    "settings": "M12,15.5A3.5,3.5 0 0,1 8.5,12A3.5,3.5 0 0,1 12,8.5A3.5,3.5 0 0,1 15.5,12A3.5,3.5 0 0,1 12,15.5M19.43,12.97C19.47,12.65 19.5,12.33 19.5,12C19.5,11.67 19.47,11.34 19.43,11L21.54,9.37C21.73,9.22 21.78,8.95 21.66,8.73L19.66,5.27C19.54,5.05 19.27,4.96 19.05,5.05L16.56,6.05C16.04,5.66 15.5,5.32 14.87,5.07L14.5,2.42C14.46,2.18 14.25,2 14,2H10C9.75,2 9.54,2.18 9.5,2.42L9.13,5.07C8.5,5.32 7.96,5.66 7.44,6.05L4.95,5.05C4.73,4.96 4.46,5.05 4.34,5.27L2.34,8.73C2.21,8.95 2.27,9.22 2.46,9.37L4.57,11C4.53,11.34 4.5,11.67 4.5,12C4.5,12.33 4.53,12.65 4.57,12.97L2.46,14.63C2.27,14.78 2.21,15.05 2.34,15.27L4.34,18.73C4.46,18.95 4.73,19.03 4.95,18.95L7.44,17.94C7.96,18.34 8.5,18.68 9.13,18.93L9.5,21.58C9.54,21.82 9.75,22 10,22H14C14.25,22 14.46,21.82 14.5,21.58L14.87,18.93C15.5,18.68 16.04,18.34 16.56,17.94L19.05,18.95C19.27,19.03 19.54,18.95 19.66,18.73L21.66,15.27C21.78,15.05 21.73,14.78 21.54,14.63L19.43,12.97Z",
    "file-document": "M13,9H18.5L13,3.5V9M6,2H14L20,8V20A2,2 0 0,1 18,22H6C4.89,22 4,21.1 4,20V4C4,2.89 4.89,2 6,2M15,18V16H6V18H15M18,14V12H6V14H18Z",
    "folder-open": "M19,20H4C2.89,20 2,19.1 2,18V6C2,4.89 2.89,4 4,4H10L12,6H19A2,2 0 0,1 21,8H21L4,8V18L6.14,10H23.21L20.93,18.5C20.7,19.37 19.92,20 19,20Z",
    "playlist-play": "M19,9H2V11H19V9M19,5H2V7H19V5M2,15H15V13H2V15M17,13V19L22,16L17,13Z",
    "plus": "M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z",
    "delete": "M19,4H15.5L14.5,3H9.5L8.5,4H5V6H19M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19Z",
    "refresh": "M17.65,6.35C16.2,4.9 14.21,4 12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20C15.73,20 18.84,17.45 19.73,14H17.65C16.83,16.33 14.61,18 12,18A6,6 0 0,1 6,12A6,6 0 0,1 12,6C13.66,6 15.14,6.69 16.22,7.78L13,11H20V4L17.65,6.35Z",
    "magnify": "M9.5,3A6.5,6.5 0 0,1 16,9.5C16,11.11 15.41,12.59 14.44,13.73L14.71,14H15.5L20.5,19L19,20.5L14,15.5V14.71L13.73,14.44C12.59,15.41 11.11,16 9.5,16A6.5,6.5 0 0,1 3,9.5A6.5,6.5 0 0,1 9.5,3M9.5,5C7,5 5,7 5,9.5C5,12 7,14 9.5,14C12,14 14,12 14,9.5C14,7 12,5 9.5,5Z",
    "filter": "M14,12V19.88C14.04,20.18 13.94,20.5 13.71,20.71C13.32,21.1 12.69,21.1 12.3,20.71L10.29,18.7C10.06,18.47 9.96,18.16 10,17.87V12H9.97L4.21,4.62C3.87,4.19 3.95,3.56 4.38,3.22C4.57,3.08 4.78,3 5,3V3H19V3C19.22,3 19.43,3.08 19.62,3.22C20.05,3.56 20.13,4.19 19.79,4.62L14.03,12H14Z",
    "sort": "M18 21L14 17H17V7H14L18 3L22 7H19V17H22M2 19V17H12V19M2 13V11H9V13M2 7V5H6V7H2Z",
    "open-in-new": "M14,3V5H17.59L7.76,14.83L9.17,16.24L19,6.41V10H21V3M19,19H5V5H12V3H5C3.89,3 3,3.9 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V12H19V19Z",
    "content-save": "M15,9H5V5H15M12,19A3,3 0 0,1 9,16A3,3 0 0,1 12,13A3,3 0 0,1 15,16A3,3 0 0,1 12,19M17,3H5C3.89,3 3,3.9 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V7L17,3Z",
    "export": "M23,12L19,8V11H10V13H19V16M1,18V6C1,4.89 1.89,4 3,4H15A2,2 0 0,1 17,6V9H15V6H3V18H15V15H17V18A2,2 0 0,1 15,20H3A2,2 0 0,1 1,18Z",
    "close": "M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z",
    "check": "M21,7L9,19L3.5,13.5L4.91,12.09L9,16.17L19.59,5.59L21,7Z",
    "folder-plus": "M13,19C13,19.7 13.13,20.37 13.35,21H5C3.89,21 3,20.1 3,19V5C3,3.89 3.89,3 5,3H9.17C9.5,2.39 10.13,2 10.83,2H13.17C13.87,2 14.5,2.39 14.83,3H19C20.1,3 21,3.9 21,5V13.35C20.37,13.13 19.7,13 19,13V5H5V19H13M23,18V20H20V23H18V20H15V18H18V15H20V18H23Z",
    "link": "M3.9,12C3.9,10.29 5.29,8.9 7,8.9H11V7H7A5,5 0 0,0 2,12A5,5 0 0,0 7,17H11V15.1H7C5.29,15.1 3.9,13.71 3.9,12M8,13H16V11H8V13M17,7H13V8.9H17C18.71,8.9 20.1,10.29 20.1,12C20.1,13.71 18.71,15.1 17,15.1H13V17H17A5,5 0 0,0 22,12A5,5 0 0,0 17,7Z",
    "microphone": "M12,2A3,3 0 0,1 15,5V11A3,3 0 0,1 12,14A3,3 0 0,1 9,11V5A3,3 0 0,1 12,2M19,11C19,14.53 16.39,17.44 13,17.93V21H11V17.93C7.61,17.44 5,14.53 5,11H7A5,5 0 0,0 12,16A5,5 0 0,0 17,11H19Z",
    "library": "M12,8A3,3 0 0,0 9,11A3,3 0 0,0 12,14A3,3 0 0,0 15,11A3,3 0 0,0 12,8M12,16.5C9.5,16.5 7.5,14.5 7.5,12C7.5,9.5 9.5,7.5 12,7.5C14.5,7.5 16.5,9.5 16.5,12C16.5,14.5 14.5,16.5 12,16.5M12,4.5C7,4.5 2.73,7.61 1,12C2.73,16.39 7,19.5 12,19.5C17,19.5 21.27,16.39 23,12C21.27,7.61 17,4.5 12,4.5Z",
    "queue-music": "M15,6H3V8H15V6M15,10H3V12H15V10M3,16H11V14H3V16M17,6V14.18C16.69,14.07 16.35,14 16,14A3,3 0 0,0 13,17A3,3 0 0,0 16,20A3,3 0 0,0 19,17V8H22V6H17Z",
    "application": "M19,4C20.11,4 21,4.9 21,6V18A2,2 0 0,1 19,20H5C3.89,20 3,19.1 3,18V6C3,4.89 3.89,4 5,4H19M19,18V8H5V18H19Z",
    "palette": "M17.5,12A1.5,1.5 0 0,1 16,10.5A1.5,1.5 0 0,1 17.5,9A1.5,1.5 0 0,1 19,10.5A1.5,1.5 0 0,1 17.5,12M14.5,8A1.5,1.5 0 0,1 13,6.5A1.5,1.5 0 0,1 14.5,5A1.5,1.5 0 0,1 16,6.5A1.5,1.5 0 0,1 14.5,8M9.5,8A1.5,1.5 0 0,1 8,6.5A1.5,1.5 0 0,1 9.5,5A1.5,1.5 0 0,1 11,6.5A1.5,1.5 0 0,1 9.5,8M6.5,12A1.5,1.5 0 0,1 5,10.5A1.5,1.5 0 0,1 6.5,9A1.5,1.5 0 0,1 8,10.5A1.5,1.5 0 0,1 6.5,12M12,3A9,9 0 0,0 3,12A9,9 0 0,0 12,21A1.5,1.5 0 0,0 13.5,19.5C13.5,19.11 13.35,18.76 13.11,18.5C12.88,18.23 12.73,17.88 12.73,17.5A1.5,1.5 0 0,1 14.23,16H16A5,5 0 0,0 21,11C21,6.58 16.97,3 12,3Z",
    "help-circle": "M12,2A10,10 0 0,1 22,12A10,10 0 0,1 12,22A10,10 0 0,1 2,12A10,10 0 0,1 12,2M12,17A1.25,1.25 0 0,0 10.75,18.25A1.25,1.25 0 0,0 12,19.5A1.25,1.25 0 0,0 13.25,18.25A1.25,1.25 0 0,0 12,17M12,6A4,4 0 0,0 8,10H10A2,2 0 0,1 12,8A2,2 0 0,1 14,10C14,11.5 12.5,12 11.75,13C11.29,13.61 11,14.37 11,15.25V16H13V15.5C13,14.95 13.22,14.45 13.59,14.09C14.5,13.17 16,12.39 16,10A4,4 0 0,0 12,6Z",
    "cog": "M12,8A4,4 0 0,1 16,12A4,4 0 0,1 12,16A4,4 0 0,1 8,12A4,4 0 0,1 12,8M12,10A2,2 0 0,0 10,12A2,2 0 0,0 12,14A2,2 0 0,0 14,12A2,2 0 0,0 12,10M10,22C9.75,22 9.54,21.82 9.5,21.58L9.13,18.93C8.5,18.68 7.96,18.34 7.44,17.94L4.95,18.95C4.73,19.03 4.46,18.95 4.34,18.73L2.34,15.27C2.21,15.05 2.27,14.78 2.46,14.63L4.57,12.97L4.5,12L4.57,11L2.46,9.37C2.27,9.22 2.21,8.95 2.34,8.73L4.34,5.27C4.46,5.05 4.73,4.96 4.95,5.05L7.44,6.05C7.96,5.66 8.5,5.32 9.13,5.07L9.5,2.42C9.54,2.18 9.75,2 10,2H14C14.25,2 14.46,2.18 14.5,2.42L14.87,5.07C15.5,5.32 16.04,5.66 16.56,6.05L19.05,5.05C19.27,4.96 19.54,5.05 19.66,5.27L21.66,8.73C21.79,8.95 21.73,9.22 21.54,9.37L19.43,11L19.5,12L19.43,13L21.54,14.63C21.73,14.78 21.79,15.05 21.66,15.27L19.66,18.73C19.54,18.95 19.27,19.04 19.05,18.95L16.56,17.95C16.04,18.34 15.5,18.68 14.87,18.93L14.5,21.58C14.46,21.82 14.25,22 14,22H10M11.25,4L10.88,6.61C9.68,6.86 8.62,7.5 7.85,8.39L5.44,7.35L4.69,8.65L6.8,10.2C6.4,11.37 6.4,12.64 6.8,13.8L4.68,15.36L5.43,16.66L7.86,15.62C8.63,16.5 9.68,17.14 10.87,17.38L11.24,20H12.76L13.13,17.39C14.32,17.14 15.37,16.5 16.14,15.62L18.57,16.66L19.32,15.36L17.2,13.81C17.6,12.64 17.6,11.37 17.2,10.2L19.31,8.65L18.56,7.35L16.15,8.39C15.38,7.5 14.32,6.86 13.12,6.62L12.75,4H11.25Z",
}


def _create_svg_icon(path_data: str, color: str, size: int = 24) -> QIcon:
    """Create a QIcon from SVG path data.

    Args:
        path_data: SVG path data string
        color: Fill color as hex string (e.g., "#333333")
        size: Icon size in pixels

    Returns:
        QIcon with the rendered SVG
    """
    svg_template = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="{size}" height="{size}" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <path d="{path_data}" fill="{color}"/>
</svg>"""

    svg_bytes = QByteArray(svg_template.encode("utf-8"))
    renderer = QSvgRenderer(svg_bytes)

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    from PySide6.QtGui import QPainter

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return QIcon(pixmap)


def get_icon(name: str, theme: str = "light", size: int = 24) -> QIcon:
    """Get an icon by name with theme support.

    Args:
        name: Icon name (e.g., "play", "settings", "folder-open")
        theme: Theme name ("light" or "dark")
        size: Icon size in pixels

    Returns:
        QIcon with the requested icon

    Raises:
        ValueError: If icon name is not found
    """
    if name not in _ICON_PATHS:
        raise ValueError(
            f"Icon '{name}' not found. Available icons: {', '.join(_ICON_PATHS.keys())}"
        )

    # Choose color based on theme
    color = "#333333" if theme == "light" else "#cccccc"

    return _create_svg_icon(_ICON_PATHS[name], color, size)


def get_icon_names() -> list[str]:
    """Return list of available icon names."""
    return list(_ICON_PATHS.keys())


# Convenience functions for common icons
def get_play_icon(theme: str = "light") -> QIcon:
    """Get play/start icon."""
    return get_icon("play", theme)


def get_stop_icon(theme: str = "light") -> QIcon:
    """Get stop/cancel icon."""
    return get_icon("stop", theme)


def get_settings_icon(theme: str = "light") -> QIcon:
    """Get settings/configuration icon."""
    return get_icon("settings", theme)


def get_library_icon(theme: str = "light") -> QIcon:
    """Get library/view icon."""
    return get_icon("library", theme)


def get_queue_icon(theme: str = "light") -> QIcon:
    """Get queue/playlist icon."""
    return get_icon("queue-music", theme)


def get_folder_icon(theme: str = "light") -> QIcon:
    """Get folder/directory icon."""
    return get_icon("folder-open", theme)


def get_add_icon(theme: str = "light") -> QIcon:
    """Get add/plus icon."""
    return get_icon("plus", theme)


def get_delete_icon(theme: str = "light") -> QIcon:
    """Get delete/remove icon."""
    return get_icon("delete", theme)


def get_refresh_icon(theme: str = "light") -> QIcon:
    """Get refresh/reload icon."""
    return get_icon("refresh", theme)


def get_search_icon(theme: str = "light") -> QIcon:
    """Get search/magnify icon."""
    return get_icon("magnify", theme)


def get_filter_icon(theme: str = "light") -> QIcon:
    """Get filter icon."""
    return get_icon("filter", theme)


def get_sort_icon(theme: str = "light") -> QIcon:
    """Get sort icon."""
    return get_icon("sort", theme)


def get_open_icon(theme: str = "light") -> QIcon:
    """Get open/external icon."""
    return get_icon("open-in-new", theme)


def get_save_icon(theme: str = "light") -> QIcon:
    """Get save icon."""
    return get_icon("content-save", theme)


def get_export_icon(theme: str = "light") -> QIcon:
    """Get export icon."""
    return get_icon("export", theme)


def get_close_icon(theme: str = "light") -> QIcon:
    """Get close icon."""
    return get_icon("close", theme)


def get_check_icon(theme: str = "light") -> QIcon:
    """Get check/confirm icon."""
    return get_icon("check", theme)


def get_microphone_icon(theme: str = "light") -> QIcon:
    """Get microphone/audio capture icon."""
    return get_icon("microphone", theme)


def get_link_icon(theme: str = "light") -> QIcon:
    """Get link/URL icon."""
    return get_icon("link", theme)


def get_document_icon(theme: str = "light") -> QIcon:
    """Get document/file icon."""
    return get_icon("file-document", theme)


def get_application_icon(theme: str = "light") -> QIcon:
    """Get application/window icon."""
    return get_icon("application", theme)


def get_palette_icon(theme: str = "light") -> QIcon:
    """Get palette/theme icon."""
    return get_icon("palette", theme)


def get_help_icon(theme: str = "light") -> QIcon:
    """Get help/support icon."""
    return get_icon("help-circle", theme)


def get_app_icon() -> QIcon:
    """Get the FlowScribe application icon.

    Returns:
        QIcon with the application icon (flowscribe.png)
    """
    if _APP_ICON_PATH.exists():
        return QIcon(str(_APP_ICON_PATH))
    # Fallback to application icon from SVG if PNG not found
    return get_icon("application", "light")
