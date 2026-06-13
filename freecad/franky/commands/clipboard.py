# SPDX-License-Identifier: LGPL-2.1-or-later

"""Command to capture and copy to clipboard a screenshot of the current view."""

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, ClassVar

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui, QtWidgets

translate = App.Qt.translate

from ..resources import Resources
from .screenshot import crop_to_content, hidden_navigation_cube


class ClipboardCommand:
    """Capture the current 3D view to the operating system clipboard."""

    Name: ClassVar[str] = "Franky_Clipboard"

    def GetResources(self) -> dict[str, str]:
        return {
            "Pixmap": Resources.icon(path="clipboard.svg"),
            "MenuText": translate(
                "Franky",
                "Copy Screenshot",
            ),
            "ToolTip": translate(
                "Franky",
                "Capture the current view to the Windows clipboard",
            ),
        }

    def Activated(self) -> None:
        doc = App.ActiveDocument
        gui_doc = Gui.ActiveDocument
        if doc is None or gui_doc is None:
            App.Console.PrintError("No active document.\n")
            return

        if not doc.FileName:
            App.Console.PrintError("Please save the document before copying a screenshot.\n")
            return

        view: Any = gui_doc.ActiveView
        if view is None:
            App.Console.PrintError("No active view.\n")
            return

        try:
            with TemporaryDirectory(prefix="freecad-clipboard") as temp_dir:
                file_path: Path = Path(temp_dir) / "clipboard.png"

                width, height = view.getSize()
                with hidden_navigation_cube(view=view):
                    view.saveImage(str(file_path), width, height, "Current")
                crop_to_content(file_path=file_path)

                image = QtGui.QImage(str(file_path))
                if image.isNull():
                    App.Console.PrintError("Could not load captured screenshot for clipboard copy.\n")
                    return

                clipboard = QtWidgets.QApplication.clipboard()
                clipboard.setImage(image)
        except Exception as error:
            App.Console.PrintError(f"Could not copy screenshot to clipboard: {error}\n")
            return

        App.Console.PrintMessage("Copied screenshot to clipboard\n")

    def IsActive(self) -> bool:
        return bool(App.ActiveDocument and Gui.ActiveDocument)

    @classmethod
    def Install(cls) -> None:
        if App.GuiUp:
            App.Gui.addCommand(cls.Name, cls())
