# SPDX-License-Identifier: LGPL-2.1-or-later

"""Command to capture and export to png a screenshot of the current view."""

from pathlib import Path
from typing import Any, ClassVar

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui

translate = App.Qt.translate

from ..resources import Resources

BACKGROUND_TOLERANCE: int = 8
CROP_PADDING: int = 8


def color_distance(first: QtGui.QColor, second: QtGui.QColor) -> int:
    """Return the largest channel difference between two colors."""
    return max(
        abs(first.red() - second.red()),
        abs(first.green() - second.green()),
        abs(first.blue() - second.blue()),
        abs(first.alpha() - second.alpha()),
    )


def crop_to_content(file_path: Path, *, tolerance: int = BACKGROUND_TOLERANCE, padding: int = CROP_PADDING) -> bool:
    """Trim background-colored pixels from the screenshot edges."""
    image = QtGui.QImage(str(file_path))
    if image.isNull():
        return False

    background = image.pixelColor(0, 0)
    left = image.width()
    top = image.height()
    right = -1
    bottom = -1

    for y in range(image.height()):
        for x in range(image.width()):
            if color_distance(image.pixelColor(x, y), background) <= tolerance:
                continue

            left = min(left, x)
            top = min(top, y)
            right = max(right, x)
            bottom = max(bottom, y)

    if right < left or bottom < top:
        return False

    left = max(left - padding, 0)
    top = max(top - padding, 0)
    right = min(right + padding, image.width() - 1)
    bottom = min(bottom + padding, image.height() - 1)

    cropped = image.copy(left, top, right - left + 1, bottom - top + 1)
    return bool(cropped.save(str(file_path), "PNG"))


class ScreenshotCommand:
    """Capture the current 3D view to a PNG file."""

    Name: ClassVar[str] = "Franky_Screenshot"

    def GetResources(self) -> dict[str, str]:
        return {
            "Pixmap": Resources.icon(path="camera.svg"),
            "MenuText": translate(
                "Franky",
                "Screenshot",
            ),
            "ToolTip": translate(
                "Franky",
                "Capture the current view to a PNG file",
            ),
        }

    def Activated(self) -> None:
        doc = App.ActiveDocument
        gui_doc = Gui.ActiveDocument
        if doc is None or gui_doc is None:
            App.Console.PrintError("No active document.\n")
            return

        if not doc.FileName:
            App.Console.PrintError("Please save the document before capturing a screenshot.\n")
            return

        view: Any = gui_doc.ActiveView
        if view is None:
            App.Console.PrintError("No active view.\n")
            return

        doc_path = Path(doc.FileName)
        file_path: Path = doc_path.parent / f"{doc_path.stem}-screenshot.png"

        try:
            width, height = view.getSize()
            if file_path.exists():
                file_path.unlink()
            view.saveImage(str(file_path), width, height, "Current")
            crop_to_content(file_path=file_path)
        except Exception as error:
            App.Console.PrintError(f"Could not capture screenshot: {error}\n")
            return

        App.Console.PrintMessage(f"Exported {file_path}\n")

    def IsActive(self) -> bool:
        return bool(App.ActiveDocument and Gui.ActiveDocument)

    @classmethod
    def Install(cls) -> None:
        if App.GuiUp:
            App.Gui.addCommand(cls.Name, cls())
