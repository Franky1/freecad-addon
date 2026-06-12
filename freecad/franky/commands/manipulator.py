# SPDX-License-Identifier: LGPL-2.1-or-later

"""Workbench manipulator."""

from __future__ import annotations

from contextlib import suppress
from typing import ClassVar

import FreeCAD as App

from .export_3mf import Export3mfCommand
from .export_bambustudio import ExportBambuStudioCommand
from .export_ideamaker import ExportIdeaMakerCommand
from .export_orcaslicer import ExportOrcaSlicerCommand
from .export_step import ExportStepCommand
from .export_stl import ExportStlCommand
from .screenshot import ScreenshotCommand


class WorkbenchManipulator:
    """Adds/Remove Commands to Gui"""

    _instance: ClassVar[WorkbenchManipulator | None] = None

    def modifyMenuBar(self) -> list[dict[str, str]]:
        """Add commands to menus."""
        return []

    def modifyContextMenu(self, recipient: str) -> list[dict[str, str]]:
        """Add commands to the context menu."""
        return []

    def modifyToolBars(self) -> list[dict[str, str]]:
        """Add commands to toolbars."""
        return [
            {"append": ExportStepCommand.Name, "toolBar": "Franky"},
            {"append": ExportStlCommand.Name, "toolBar": "Franky"},
            {"append": Export3mfCommand.Name, "toolBar": "Franky"},
            {"append": ExportIdeaMakerCommand.Name, "toolBar": "Franky"},
            {"append": ExportBambuStudioCommand.Name, "toolBar": "Franky"},
            {"append": ExportOrcaSlicerCommand.Name, "toolBar": "Franky"},
            {"append": ScreenshotCommand.Name, "toolBar": "Franky"},
        ]

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
