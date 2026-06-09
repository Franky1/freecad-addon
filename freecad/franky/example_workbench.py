# SPDX-License-Identifier: LGPL-2.1-or-later

"""Example FreeCAD Workbench."""

import FreeCADGui as Gui

import FreeCAD as App

translate = App.Qt.translate

from .commands import ExampleCommand
from .resources import Resources


class FrankyWorkbench(Gui.Workbench):
    MenuText: str = translate(
        "Franky",
        "Example Workbench",
    )

    ToolTip: str = translate(
        "Franky",
        "Example Workbench tooltip",
    )

    Icon: str = Resources.icon("franky-wb.svg")

    def Initialize(self) -> None:
        App.Console.PrintMessage("Example Workbench initialized\n")
        # Adding menus and toolbars when the Workbench is active (example)
        commands = [ExampleCommand.Name]
        self.appendToolbar("Franky", commands)
        self.appendMenu("Franky", commands)

    def Activated(self) -> None:
        App.Console.PrintMessage("Example Workbench activated\n")

    def Deactivated(self) -> None:
        App.Console.PrintMessage("Example Workbench deactivated\n")

    def ContextMenu(self, recipient: str) -> None:
        App.Console.PrintMessage("Example Workbench context menu\n")
        # Adding context menus when the Workbench is active (example)
        self.appendContextMenu("", [ExampleCommand.Name])

    @classmethod
    def Install(cls) -> None:
        Gui.addWorkbench(cls)
