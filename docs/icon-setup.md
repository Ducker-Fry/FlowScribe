# Application Icon Setup

FlowScribe uses a custom application icon located at `icons/flowscribe.png`.

## Current Implementation

The application icon is loaded from `icons/flowscribe.png` and set as:
- Window icon (title bar)
- Taskbar icon
- Application icon in task switcher

## Icon Formats

### PNG (Current)
- **Location**: `icons/flowscribe.png`
- **Usage**: Runtime window icon
- **Supported**: ✅ Works on all platforms (Windows, macOS, Linux)

### ICO (Recommended for Windows)
For better Windows integration, especially for:
- Executable file icon
- Better taskbar appearance
- Windows Explorer icon

### Converting PNG to ICO

You can convert the PNG to ICO format using:

**Online tools:**
- https://convertio.co/png-ico/
- https://www.icoconverter.com/

**Command line (ImageMagick):**
```bash
magick convert flowscribe.png -define icon:auto-resize=256,128,64,48,32,16 flowscribe.ico
```

**Python (Pillow):**
```python
from PIL import Image

img = Image.open('icons/flowscribe.png')
img.save('icons/flowscribe.ico', format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
```

## Build Integration

When building the executable with PyInstaller, add the icon:

**In `scripts/build_gui_exe.ps1`:**
```powershell
pyinstaller `
    --icon="icons/flowscribe.ico" `
    --name="FlowScribeGUI" `
    # ... other options
```

## Icon Sizes

The icon should include multiple sizes for different contexts:
- **256×256**: High DPI displays, Windows 10/11
- **128×128**: Large icons
- **64×64**: Standard desktop icons
- **48×48**: Windows Explorer
- **32×32**: Taskbar, title bar
- **16×16**: Small icons, menus

## Testing

Run the GUI to verify the icon appears correctly:
```powershell
python -m flowscribe.gui
```

Check:
- ✅ Window title bar icon
- ✅ Taskbar icon
- ✅ Alt+Tab task switcher icon
- ✅ Icon scales properly at different sizes
