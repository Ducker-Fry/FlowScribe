"""Convert FlowScribe PNG icon to ICO format for Windows.

This script converts the PNG icon to ICO format with multiple sizes
for better Windows integration.

Requirements:
    pip install Pillow
"""

from __future__ import annotations

import sys
from pathlib import Path

# Set UTF-8 encoding for stdout
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is not installed.")
    print("Install it with: pip install Pillow")
    sys.exit(1)


def convert_png_to_ico(png_path: Path, ico_path: Path) -> None:
    """Convert PNG to ICO with multiple sizes.

    Args:
        png_path: Path to source PNG file
        ico_path: Path to output ICO file
    """
    if not png_path.exists():
        print(f"Error: PNG file not found at {png_path}")
        sys.exit(1)

    print(f"Loading PNG from {png_path}...")
    img = Image.open(png_path)

    # Convert to RGBA if not already
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # Icon sizes for Windows
    sizes = [
        (256, 256),  # High DPI displays, Windows 10/11
        (128, 128),  # Large icons
        (64, 64),  # Standard desktop icons
        (48, 48),  # Windows Explorer
        (32, 32),  # Taskbar, title bar
        (16, 16),  # Small icons, menus
    ]

    print(f"Converting to ICO with sizes: {sizes}...")
    img.save(ico_path, format="ICO", sizes=sizes)

    print(f"[OK] Successfully created {ico_path}")
    print(f"  File size: {ico_path.stat().st_size / 1024:.1f} KB")


def main():
    """Convert FlowScribe icon."""
    # Paths relative to project root
    project_root = Path(__file__).parent.parent
    png_path = project_root / "icons" / "flowscribe.png"
    ico_path = project_root / "icons" / "flowscribe.ico"

    print("FlowScribe Icon Converter")
    print("=" * 50)

    convert_png_to_ico(png_path, ico_path)

    print("\nNext steps:")
    print("1. Update build scripts to use --icon=icons/flowscribe.ico")
    print("2. Rebuild the executable")
    print("3. Verify the icon appears in Windows Explorer")


if __name__ == "__main__":
    main()
