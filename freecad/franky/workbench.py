# SPDX-License-Identifier: LGPL-2.1-or-later

"""FreeCAD Workbench."""

import FreeCADGui as Gui

import FreeCAD as App

translate = App.Qt.translate

from .commands import (
    ExampleCommand,
    Export3mfCommand,
    ExportBambuStudioCommand,
    ExportIdeaMakerCommand,
    ExportOrcaSlicerCommand,
    ExportStepCommand,
    ExportStlCommand,
)
from .resources import Resources


class FrankyWorkbench(Gui.Workbench):
    MenuText: str = translate(
        "Franky",
        "Franky Workbench",
    )

    ToolTip: str = translate(
        "Franky",
        "Franky Workbench tooltip",
    )

    Icon: str = Resources.icon(path="franky-wb.svg")

    def Initialize(self) -> None:
        App.Console.PrintMessage("Franky Workbench initialized\n")
        # Adding menus and toolbars when the Workbench is active (example)
        commands: list[str] = [
            ExampleCommand.Name,
            ExportStepCommand.Name,
            ExportStlCommand.Name,
            Export3mfCommand.Name,
            ExportBambuStudioCommand.Name,
            ExportIdeaMakerCommand.Name,
            ExportOrcaSlicerCommand.Name,
        ]
        self.appendToolbar("Franky", commands)
        self.appendMenu("Franky", commands)

    def Activated(self) -> None:
        App.Console.PrintMessage("Franky Workbench activated\n")

    def Deactivated(self) -> None:
        App.Console.PrintMessage("Franky Workbench deactivated\n")

    def ContextMenu(self, recipient: str) -> None:
        App.Console.PrintMessage("Franky Workbench context menu\n")
        # Adding context menus when the Workbench is active (example)
        self.appendContextMenu("", [ExampleCommand.Name])

    @classmethod
    def Install(cls) -> None:
        Gui.addWorkbench(cls)
