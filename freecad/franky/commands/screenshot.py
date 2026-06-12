# SPDX-License-Identifier: LGPL-2.1-or-later

"""Command to capture and export to png a screenshot of the current view."""

from pathlib import Path
from typing import Any, ClassVar

import FreeCAD as App
import FreeCADGui as Gui

translate = App.Qt.translate

from ..resources import Resources


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
