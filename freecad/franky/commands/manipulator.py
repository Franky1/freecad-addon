# SPDX-License-Identifier: LGPL-2.1-or-later

"""Workbench manipulator."""

from __future__ import annotations

from contextlib import suppress
from typing import ClassVar

import FreeCAD as App

from .example_command import ExampleCommand
from .export_3mf import Export3mfCommand
from .export_bambustudio import ExportBambuStudioCommand
from .export_ideamaker import ExportIdeaMakerCommand
from .export_orcaslicer import ExportOrcaSlicerCommand
from .export_step import ExportStepCommand
from .export_stl import ExportStlCommand


class WorkbenchManipulator:
    """Adds/Remove Commands to Gui"""

    _instance: ClassVar[WorkbenchManipulator | None]  = None

    def modifyMenuBar(self) -> list[dict[str, str]]:
        """Add commands to menus."""
        return []

    def modifyContextMenu(self, recipient: str) -> list[dict[str, str]]:
        """Add commands to the context menu."""
        return []

    def modifyToolBars(self) -> list[dict[str, str]]:
        """Add commands to toolbars."""
        # Add our commands to the File toolbar so they are available in any workbench
        # return [
        #     {"append": ExampleCommand.Name, "toolBar": "File"},
        #     {"append": ExportStepCommand.Name, "toolBar": "File"},
        #     {"append": ExportStlCommand.Name, "toolBar": "File"},
        #     {"append": Export3mfCommand.Name, "toolBar": "File"},
        #     {"append": ExportBambuStudioCommand.Name, "toolBar": "File"},
        #     {"append": ExportIdeaMakerCommand.Name, "toolBar": "File"},
        #     {"append": ExportOrcaSlicerCommand.Name, "toolBar": "File"},
        # ]
        return []

    # Optional but useful (good practice to encapsulate here)
    @classmethod
    def install(cls) -> None:
        """Apply the workbench manipulator to the live session"""
        if App.GuiUp and cls._instance is None:
            cls._instance = WorkbenchManipulator()
            App.Gui.addWorkbenchManipulator(cls._instance)
            with suppress(Exception):
                App.Gui.activeWorkbench().reloadActive()

    # Optional but useful (good practice to encapsulate here)
    @classmethod
    def uninstall(cls) -> None:
        """Remove the workbench manipulator to the live session"""
        if App.GuiUp and cls._instance is not None:
            App.Gui.removeWorkbenchManipulator(cls._instance)
            cls._instance = None
            with suppress(Exception):
                App.Gui.activeWorkbench().reloadActive()
