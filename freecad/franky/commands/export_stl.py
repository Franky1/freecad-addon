# SPDX-License-Identifier: LGPL-2.1-or-later

"""Command to export the selected objects to STL files."""

from pathlib import Path
from typing import ClassVar

import FreeCADGui as Gui
import Mesh

import FreeCAD as App

translate = App.Qt.translate

from ..resources import Resources

class ExportStlCommand:
    """Export the selected objects to STL files."""

    Name: ClassVar[str] = "Franky_ExportStl"

    def GetResources(self) -> dict[str, str]:
        return {
            "Pixmap": Resources.icon(path="export2stl.png"),
            "MenuText": translate(
                "Franky",
                "Export to STL",
            ),
            "ToolTip": translate(
                "Franky",
                "Export the selected objects to STL files",
            ),
        }

    def Activated(self) -> None:
        doc = App.ActiveDocument
        if doc is None:
            App.Console.PrintError("No active document.\n")
            return

        objects_to_export = Gui.Selection.getSelection()
        if not objects_to_export:
            App.Console.PrintError("No objects selected.\n")
            return

        if not doc.FileName:
            App.Console.PrintError("Please save the document before exporting.\n")
            return

        App.Console.PrintMessage("Running ExportStl...\n")

        doc_path = Path(doc.FileName)
        filename: str = doc_path.stem
        output_dir: Path = doc_path.parent

        for obj in objects_to_export:
            file_path: Path = output_dir / f"{filename}-{obj.Label}.stl"
            if file_path.exists():
                file_path.unlink()
            Mesh.export([obj], str(file_path))
            App.Console.PrintMessage(f"Exported {file_path}\n")

    def IsActive(self) -> bool:
        return bool(App.ActiveDocument and Gui.Selection.getSelection())

    @classmethod
    def Install(cls) -> None:
        if App.GuiUp:
            App.Gui.addCommand(cls.Name, cls())
