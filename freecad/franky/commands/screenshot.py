# SPDX-License-Identifier: LGPL-2.1-or-later

"""Command to capture and export to png a screenshot of the current view."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, ClassVar

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui

translate = App.Qt.translate

from ..resources import Resources

BACKGROUND_TOLERANCE: int = 8
CROP_PADDING_RATIO: float = 0.1
NAVICUBE_PARAM_PATH: str = "User parameter:BaseApp/Preferences/View"
NAVICUBE_ENABLED_PARAM: str = "ShowNaviCube"


def color_distance(first: QtGui.QColor, second: QtGui.QColor) -> int:
    """Return the largest channel difference between two colors."""
    return max(
        abs(first.red() - second.red()),
        abs(first.green() - second.green()),
        abs(first.blue() - second.blue()),
        abs(first.alpha() - second.alpha()),
    )


def refresh_view(view: Any) -> None:
    """Ask FreeCAD to repaint the active view."""
    redraw = getattr(view, "redraw", None)
    if callable(redraw):
        redraw()
    QtGui.QApplication.processEvents()
    Gui.updateGui()


@contextmanager
def hidden_navigation_cube(view: Any) -> Iterator[None]:
    """Temporarily hide the FreeCAD navigation cube."""
    parameters = App.ParamGet(NAVICUBE_PARAM_PATH)
    was_enabled = bool(parameters.GetBool(NAVICUBE_ENABLED_PARAM, True))

    parameters.SetBool(NAVICUBE_ENABLED_PARAM, False)
    refresh_view(view=view)
    try:
        yield
    finally:
        parameters.SetBool(NAVICUBE_ENABLED_PARAM, was_enabled)
        refresh_view(view=view)


def crop_to_content(
    file_path: Path,
    *,
    tolerance: int = BACKGROUND_TOLERANCE,
    padding_ratio: float = CROP_PADDING_RATIO,
) -> bool:
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

    content_width = right - left + 1
    content_height = bottom - top + 1
    padding_x = round(content_width * padding_ratio)
    padding_y = round(content_height * padding_ratio)

    left = max(left - padding_x, 0)
    top = max(top - padding_y, 0)
    right = min(right + padding_x, image.width() - 1)
    bottom = min(bottom + padding_y, image.height() - 1)

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
            with hidden_navigation_cube(view=view):
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
