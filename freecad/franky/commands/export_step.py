# SPDX-License-Identifier: LGPL-2.1-or-later

"""Command to export the selected objects to STEP files."""

from pathlib import Path
from typing import ClassVar

import FreeCADGui as Gui
import ImportGui

import FreeCAD as App

translate = App.Qt.translate

from ..resources import Resources
from .selection import contains_only_bodies

class ExportStepCommand:
    """Export the selected objects to STEP files."""

    Name: ClassVar[str] = "Franky_ExportStep"

    def GetResources(self) -> dict[str, str]:
        return {
            "Pixmap": Resources.icon(path="export2step.png"),
            "MenuText": translate(
                "Franky",
                "Export to STEP",
            ),
            "ToolTip": translate(
                "Franky",
                "Export the selected objects to STEP files",
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

        if not contains_only_bodies(objects=objects_to_export):
            App.Console.PrintError("Please select only Body objects before exporting.\n")
            return

        if not doc.FileName:
            App.Console.PrintError("Please save the document before exporting.\n")
            return

        App.Console.PrintMessage("Running ExportStep...\n")

        doc_path = Path(doc.FileName)
        filename: str = doc_path.stem
        output_dir: Path = doc_path.parent

        for obj in objects_to_export:
            file_path: Path = output_dir / f"{filename}-{obj.Label}.step"
            if file_path.exists():
                file_path.unlink()
            ImportGui.export([obj], str(file_path))
            App.Console.PrintMessage(f"Exported {file_path}\n")

    def IsActive(self) -> bool:
        objects_to_export = Gui.Selection.getSelection()
        return bool(App.ActiveDocument and objects_to_export and contains_only_bodies(objects=objects_to_export))

    @classmethod
    def Install(cls) -> None:
        if App.GuiUp:
            App.Gui.addCommand(cls.Name, cls())
