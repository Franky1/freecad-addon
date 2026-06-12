# SPDX-License-Identifier: LGPL-2.1-or-later

"""FreeCAD Workbench."""

import FreeCADGui as Gui

import FreeCAD as App

translate = App.Qt.translate

from .commands import (
    Export3mfCommand,
    ExportBambuStudioCommand,
    ExportIdeaMakerCommand,
    ExportOrcaSlicerCommand,
    ExportStepCommand,
    ExportStlCommand,
    ScreenshotCommand,
)
from .resources import Resources


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
        ]
        self.appendMenu("Franky", commands)

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
        Gui.addWorkbench(cls)
