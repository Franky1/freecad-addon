# SPDX-License-Identifier: LGPL-2.1-or-later

"""FreeCAD Workbench."""

import platform

import FreeCAD as App
import FreeCADGui as Gui

translate = App.Qt.translate

from .commands import (
    ClipboardCommand,
    Export3mfCommand,
    ExportBambuStudioCommand,
    ExportIdeaMakerCommand,
    ExportOrcaSlicerCommand,
    ExportStepCommand,
    ExportStlCommand,
    NewProjectCommand,
    ScreenshotCommand,
    VarSetQuickEditCommand,
)
from .resources import Resources

_TESTED_FREECAD_RELEASE_VERSION: tuple[int, int, int] = (1, 1, 1)
_MINIMUM_TESTED_FREECAD_DEV_VERSION: tuple[int, int, int] = (1, 2, 0)


def _parse_version_part(version_part: object) -> int | None:
    version_text = str(version_part)
    digits = ""

    for char in version_text:
        if char.isdigit():
            digits += char
        elif digits:
            break

    if not digits:
        return None

    return int(digits)


def _freecad_version() -> tuple[tuple[int, int, int] | None, str]:
    version_parts = tuple(str(part) for part in App.Version()[:3])
    version_text = ".".join(version_parts) or "unknown"

    if len(version_parts) < 3:
        return None, version_text

    major = _parse_version_part(version_parts[0])
    minor = _parse_version_part(version_parts[1])
    patch = _parse_version_part(version_parts[2])

    if major is None or minor is None or patch is None:
        return None, version_text

    return (major, minor, patch), version_text


def _is_tested_freecad_version(version: tuple[int, int, int]) -> bool:
    return version == _TESTED_FREECAD_RELEASE_VERSION or version >= _MINIMUM_TESTED_FREECAD_DEV_VERSION


def _print_compatibility_warnings() -> None:
    freecad_version, freecad_version_text = _freecad_version()

    if freecad_version is None or not _is_tested_freecad_version(version=freecad_version):
        App.Console.PrintWarning(
            "Franky Workbench has been tested with FreeCAD 1.1.1 and 1.2.0dev or later; "
            f"FreeCAD {freecad_version_text} is untested and may not work as expected.\n",
        )

    operating_system = platform.system()
    if operating_system != "Windows":
        App.Console.PrintWarning(
            "Franky Workbench has been tested on Windows only; some functions are untested and will not "
            f"work under {operating_system or 'this operating system'}.\n",
        )


class FrankyWorkbench(Gui.Workbench):
    MenuText: str = translate(
        "Franky",
        "Franky",
    )

    ToolTip: str = translate(
        "Franky",
        "Franky Personal FreeCAD AddOn",
    )

    Icon: str = Resources.icon(path="franky.svg")

    def Initialize(self) -> None:
        App.Console.PrintMessage("Franky Workbench initialized\n")
        # Adding menus and toolbars when the Workbench is active (example)
        commands: list[str] = [
            ExportStepCommand.Name,
            ExportStlCommand.Name,
            Export3mfCommand.Name,
            ExportIdeaMakerCommand.Name,
            ExportBambuStudioCommand.Name,
            ExportOrcaSlicerCommand.Name,
            ScreenshotCommand.Name,
            ClipboardCommand.Name,
            VarSetQuickEditCommand.Name,
            NewProjectCommand.Name,
        ]
        self.appendMenu("Franky", commands)
        self.appendToolbar("Franky", commands)

    def Activated(self) -> None:
        App.Console.PrintMessage("Franky Workbench activated\n")

    def Deactivated(self) -> None:
        App.Console.PrintMessage("Franky Workbench deactivated\n")

    def ContextMenu(self, recipient: str) -> None:
        App.Console.PrintMessage("Franky Workbench context menu\n")
        # Adding context menus when the Workbench is active (example)
        self.appendContextMenu("", [ExportStepCommand.Name])

    @classmethod
    def Install(cls) -> None:
        if not App.GuiUp:
            return

        _print_compatibility_warnings()
        Gui.addWorkbench(cls)
