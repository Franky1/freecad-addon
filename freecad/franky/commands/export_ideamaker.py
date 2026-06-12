# SPDX-License-Identifier: LGPL-2.1-or-later

"""Command to export the selected objects to STEP and open them in IdeaMaker."""

import os
import subprocess
from pathlib import Path
from typing import ClassVar

import FreeCADGui as Gui
import ImportGui

import FreeCAD as App

translate = App.Qt.translate

from ..resources import Resources
from .selection import contains_only_bodies

def get_ideamaker_path() -> Path:
    """Return the absolute path to the IdeaMaker executable.

    Raises:
        FileNotFoundError: If IdeaMaker could not be located.
    """
    base_dirs: list[str | None] = [
        os.environ.get(key="PROGRAMFILES"),
        os.environ.get(key="PROGRAMFILES(X86)"),
        os.environ.get(key="LOCALAPPDATA"),
    ]
    suffixes: list[Path] = [
        Path("Raise3D") / "ideaMaker" / "ideaMaker.exe",
        Path("Raise3D") / "ideaMaker-App" / "ideaMaker.exe",
    ]

    for base_dir in base_dirs:
        if not base_dir:
            continue
        root = Path(base_dir)
        for suffix in suffixes:
            install_candidate: Path = root / suffix
            if install_candidate.is_file():
                return install_candidate

    raise FileNotFoundError("Could not locate IdeaMaker.exe.")


class ExportIdeaMakerCommand:
    """Export the selected objects to STEP files and open them in IdeaMaker."""

    Name: ClassVar[str] = "Franky_Export2IdeaMaker"

    def GetResources(self) -> dict[str, str]:
        return {
            "Pixmap": Resources.icon(path="export2ideamaker.svg"),
            "MenuText": translate(
                "Franky",
                "Export to IdeaMaker",
            ),
            "ToolTip": translate(
                "Franky",
                "Export the selected objects to STEP and open them in IdeaMaker",
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

        try:
            ideamaker_path: Path = get_ideamaker_path()
        except FileNotFoundError as error:
            App.Console.PrintError(f"{error}\n")
            return

        slicer_args: list[str] = [str(ideamaker_path)]

        App.Console.PrintMessage("Running Export2IdeaMaker...\n")

        doc_path = Path(doc.FileName)
        filename: str = doc_path.stem
        output_dir: Path = doc_path.parent

        for obj in objects_to_export:
            file_path: Path = output_dir / f"{filename}-{obj.Label}.step"
            if file_path.exists():
                file_path.unlink()
            ImportGui.export([obj], str(file_path))
            slicer_args.append(str(file_path))

        subprocess.Popen(args=slicer_args)

    def IsActive(self) -> bool:
        objects_to_export = Gui.Selection.getSelection()
        return bool(App.ActiveDocument and objects_to_export and contains_only_bodies(objects=objects_to_export))

    @classmethod
    def Install(cls) -> None:
        if App.GuiUp:
            App.Gui.addCommand(cls.Name, cls())
