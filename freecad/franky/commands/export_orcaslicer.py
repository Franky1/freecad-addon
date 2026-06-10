# SPDX-License-Identifier: LGPL-2.1-or-later

"""Command to export the selected objects to STEP and open them in IdeaMaker."""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import ClassVar

import FreeCADGui as Gui
import ImportGui

import FreeCAD as App

translate = App.Qt.translate

from ..resources import Resources

# Where to write the intermediate STEP files:
#   False -> next to the FreeCAD document (.FCStd)
#   True  -> in the system temp folder
SAVE_TO_TEMP: bool = False


def get_orcaslicer_path() -> Path:
    """Return the absolute path to the OrcaSlicer executable.

    Raises:
        FileNotFoundError: If OrcaSlicer could not be located.
    """
    base_dirs: list[str | None] = [
        os.environ.get("PROGRAMFILES"),
        os.environ.get("PROGRAMFILES(X86)"),
        os.environ.get("LOCALAPPDATA"),
    ]
    suffixes: list[Path] = [
        Path("OrcaSlicer") / "OrcaSlicer.exe",
        Path("OrcaSlicer-App") / "OrcaSlicer.exe",
    ]

    for base_dir in base_dirs:
        if not base_dir:
            continue
        root = Path(base_dir)
        for suffix in suffixes:
            install_candidate: Path = root / suffix
            if install_candidate.is_file():
                return install_candidate

    raise FileNotFoundError("Could not locate OrcaSlicer.exe.")


class ExportOrcaSlicerCommand:
    """Export the selected objects to STEP files and open them in OrcaSlicer."""

    Name: ClassVar[str] = "Franky_Export2OrcaSlicer"

    def GetResources(self) -> dict[str, str]:
        return {
            "Pixmap": Resources.icon(path="export2orcaslicer.svg"),
            "MenuText": translate(
                "Franky",
                "Export to OrcaSlicer",
            ),
            "ToolTip": translate(
                "Franky",
                "Export the selected objects to STEP and open them in OrcaSlicer",
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

        try:
            orcaslicer_path: Path = get_orcaslicer_path()
        except FileNotFoundError as error:
            App.Console.PrintError(f"{error}\n")
            return

        slicer_args: list[str] = [str(orcaslicer_path)]

        App.Console.PrintMessage("Running Export2OrcaSlicer...\n")

        doc_path = Path(doc.FileName)
        filename: str = doc_path.stem
        output_dir: Path = Path(tempfile.gettempdir()) if SAVE_TO_TEMP else doc_path.parent

        for obj in objects_to_export:
            file_path: Path = output_dir / f"{filename}-{obj.Label}.step"
            if file_path.exists():
                file_path.unlink()
            ImportGui.export([obj], str(file_path))
            slicer_args.append(str(file_path))

        subprocess.Popen(args=slicer_args)

    def IsActive(self) -> bool:
        return bool(App.ActiveDocument and Gui.Selection.getSelection())

    @classmethod
    def Install(cls) -> None:
        if App.GuiUp:
            App.Gui.addCommand(cls.Name, cls())
