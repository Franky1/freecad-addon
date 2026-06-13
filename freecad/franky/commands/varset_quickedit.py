# SPDX-License-Identifier: LGPL-2.1-or-later

"""Command to quickly edit variable sets in a more user-friendly way than the default FreeCAD interface."""

import keyword
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

translate = App.Qt.translate

from ..resources import Resources

VARIABLE_GROUP: str = "Variables"
STANDARD_VARSET_PROPERTIES: frozenset[str] = frozenset({"ExpressionEngine", "Label", "Label2", "Visibility"})
PROPERTY_TYPES: tuple[str, ...] = (
    "App::PropertyBool",
    "App::PropertyInteger",
    "App::PropertyFloat",
    "App::PropertyString",
    "App::PropertyQuantity",
    "App::PropertyLength",
    "App::PropertyDistance",
    "App::PropertyAngle",
    "App::PropertyArea",
    "App::PropertyVolume",
    "App::PropertyPercent",
)
COLUMN_MINIMUM_WIDTHS: tuple[int, int, int, int] = (160, 160, 180, 280)
COLUMN_PADDING: int = 32
MAX_SCREEN_RATIO: float = 0.85


@dataclass
class VariableInfo:
    """Editable VarSet property metadata."""

    name: str
    type_id: str
    tooltip: str


def is_varset(obj: Any) -> bool:
    """Return whether the object looks like a FreeCAD variable set."""
    is_derived_from = getattr(obj, "isDerivedFrom", None)
    if callable(is_derived_from):
        try:
            if bool(is_derived_from("App::VarSet")):
                return True
        except Exception:
            pass

    type_id = str(getattr(obj, "TypeId", ""))
    return type_id == "App::VarSet" or type_id.endswith("::VarSet")


def get_property_text(obj: Any, method_name: str, property_name: str) -> str:
    """Return property metadata from FreeCAD if the object exposes it."""
    method = getattr(obj, method_name, None)
    if not callable(method):
        return ""

    try:
        value = method(property_name)
    except Exception:
        return ""

    return "" if value is None else str(value)


def get_property_status(obj: Any, property_name: str) -> list[Any]:
    """Return FreeCAD property status flags."""
    method = getattr(obj, "getPropertyStatus", None)
    if not callable(method):
        return []

    try:
        status = method(property_name)
    except Exception:
        return []

    return list(status) if isinstance(status, list | tuple) else [status]


def is_variable_property(obj: Any, property_name: str) -> bool:
    """Return whether a VarSet property should be shown as a user variable."""
    if property_name in STANDARD_VARSET_PROPERTIES:
        return False

    if get_property_text(obj, "getGroupOfProperty", property_name) == VARIABLE_GROUP:
        return True

    status = get_property_status(obj=obj, property_name=property_name)
    return 21 in status or "Dynamic" in status


def find_varsets(document: Any) -> list[Any]:
    """Find all variable sets in the active document."""
    return [obj for obj in getattr(document, "Objects", []) if is_varset(obj)]


def list_variables(varset: Any) -> list[VariableInfo]:
    """List editable variables from a VarSet object."""
    variables: list[VariableInfo] = []
    for property_name in getattr(varset, "PropertiesList", []):
        if not is_variable_property(obj=varset, property_name=property_name):
            continue

        variables.append(
            VariableInfo(
                name=str(property_name),
                type_id=get_property_text(varset, "getTypeIdOfProperty", property_name),
                tooltip=get_property_text(varset, "getDocumentationOfProperty", property_name),
            )
        )

    return variables


def stringify_value(value: Any) -> str:
    """Return a stable editable string for a FreeCAD property value."""
    if value is None:
        return ""

    return str(value)


def parse_value(type_id: str, text: str) -> Any:
    """Parse text from the editor into a value suitable for a FreeCAD property."""
    stripped = text.strip()

    if type_id == "App::PropertyBool":
        lowered = stripped.lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"", "0", "false", "no", "off"}:
            return False
        msg = "Expected a boolean value."
        raise ValueError(msg)

    if type_id in {"App::PropertyInteger", "App::PropertyPercent"}:
        return int(stripped or "0")

    if type_id == "App::PropertyFloat":
        return float(stripped or "0")

    if type_id == "App::PropertyString":
        return text

    if type_id in {
        "App::PropertyQuantity",
        "App::PropertyLength",
        "App::PropertyDistance",
        "App::PropertyAngle",
        "App::PropertyArea",
        "App::PropertyVolume",
    }:
        return App.Units.Quantity(stripped or "0")

    return text


def set_property_value(obj: Any, property_name: str, value: Any) -> None:
    """Set a FreeCAD property by name."""
    setattr(obj, property_name, value)


def validate_property_name(name: str) -> bool:
    """Return whether the name is a safe FreeCAD property identifier."""
    return bool(name) and name.isidentifier() and not keyword.iskeyword(name)


def run_transaction(document: Any, label: str, action: Callable[[], None]) -> None:
    """Run a FreeCAD document edit as one undoable transaction."""
    document.openTransaction(label)
    try:
        action()
    except Exception:
        document.abortTransaction()
        raise

    document.commitTransaction()
    document.recompute()


class VarSetQuickEditDialog(QtWidgets.QDialog):
    """Dialog for editing variables from document variable sets."""

    def __init__(self, document: Any, parent: Any = None) -> None:
        super().__init__(parent)
        self.document: Any = document
        self.varsets: dict[str, Any] = {}
        self.variables: list[VariableInfo] = []
        self.loading: bool = False

        self.setWindowTitle(translate("Franky", "VarSet Quick Edit"))
        self.setWindowIcon(QtGui.QIcon(Resources.icon(path="brackets.svg")))
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)

        self.varset_combo = QtWidgets.QComboBox(parent=self)
        self.varset_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.varset_combo.currentIndexChanged.connect(self._selected_varset_changed)

        self.table = QtWidgets.QTableWidget(parent=self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            [
                translate("Franky", "Name"),
                translate("Franky", "Value"),
                translate("Franky", "Type"),
                translate("Franky", "Tooltip"),
            ]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.itemChanged.connect(self._item_changed)

        selector_layout = QtWidgets.QHBoxLayout()
        selector_layout.addWidget(QtWidgets.QLabel(translate("Franky", "VarSet"), parent=self))
        selector_layout.addWidget(self.varset_combo, 1)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(selector_layout)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.refresh(document=document)

    def refresh(self, document: Any | None = None) -> None:
        """Refresh document VarSets and reload the selected table."""
        if document is not None:
            self.document = document

        current_name = self._selected_varset_name()
        self.loading = True
        self.varset_combo.clear()
        self.varsets = {}

        for varset in find_varsets(document=self.document):
            name = str(getattr(varset, "Name", ""))
            self.varsets[name] = varset
            self.varset_combo.addItem(self._varset_label(varset), name)

        if current_name:
            index = self.varset_combo.findData(current_name)
            if index >= 0:
                self.varset_combo.setCurrentIndex(index)

        self.loading = False
        self._load_selected_varset()

    def _selected_varset_changed(self, _index: int) -> None:
        if self.loading:
            return

        self._load_selected_varset()

    def _selected_varset_name(self) -> str:
        data = self.varset_combo.itemData(self.varset_combo.currentIndex())
        return "" if data is None else str(data)

    def _selected_varset(self) -> Any | None:
        return self.varsets.get(self._selected_varset_name())

    def _load_selected_varset(self) -> None:
        self.loading = True
        self.variables = []
        self.table.setRowCount(0)

        varset = self._selected_varset()
        if varset is not None:
            self.variables = list_variables(varset=varset)
            self.table.setRowCount(len(self.variables))
            for row, variable in enumerate(self.variables):
                self._set_text_item(row=row, column=0, text=variable.name)
                self._set_text_item(row=row, column=1, text=self._property_value_text(varset, variable.name))
                self._set_type_combo(row=row, variable=variable)
                self._set_text_item(row=row, column=3, text=variable.tooltip)

        self.loading = False
        self._resize_to_contents()

    def _set_text_item(self, row: int, column: int, text: str) -> None:
        item = QtWidgets.QTableWidgetItem(text)
        item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
        self.table.setItem(row, column, item)

    def _set_type_combo(self, row: int, variable: VariableInfo) -> None:
        combo = QtWidgets.QComboBox(parent=self.table)
        type_ids = list(PROPERTY_TYPES)
        if variable.type_id and variable.type_id not in type_ids:
            type_ids.insert(0, variable.type_id)

        combo.addItems(type_ids)
        combo.setCurrentText(variable.type_id)
        combo.currentIndexChanged.connect(
            lambda _index, combo=combo, row=row: self._type_changed(row=row, type_id=combo.currentText())
        )
        self.table.setCellWidget(row, 2, combo)

    def _property_value_text(self, varset: Any, property_name: str) -> str:
        try:
            return stringify_value(varset.getPropertyByName(property_name))
        except Exception:
            return ""

    def _item_changed(self, item: Any) -> None:
        if self.loading:
            return

        row = int(item.row())
        column = int(item.column())
        if column == 0:
            self._rename_variable(row=row, new_name=item.text().strip())
        elif column == 1:
            self._change_value(row=row, text=item.text())
        elif column == 3:
            self._change_tooltip(row=row, text=item.text())

        self._resize_to_contents()

    def _rename_variable(self, row: int, new_name: str) -> None:
        varset = self._selected_varset()
        variable = self._variable_at(row=row)
        if varset is None or variable is None or new_name == variable.name:
            return

        if not validate_property_name(new_name):
            self._reset_text(row=row, column=0, text=variable.name)
            App.Console.PrintError("Variable names must be valid Python-style identifiers.\n")
            return

        if new_name in getattr(varset, "PropertiesList", []):
            self._reset_text(row=row, column=0, text=variable.name)
            App.Console.PrintError(f"Variable '{new_name}' already exists.\n")
            return

        try:
            run_transaction(
                document=self.document,
                label=translate("Franky", "Rename VarSet variable"),
                action=lambda: varset.renameProperty(variable.name, new_name),
            )
        except Exception as error:
            self._reset_text(row=row, column=0, text=variable.name)
            App.Console.PrintError(f"Could not rename variable '{variable.name}': {error}\n")
            return

        variable.name = new_name

    def _change_value(self, row: int, text: str) -> None:
        varset = self._selected_varset()
        variable = self._variable_at(row=row)
        if varset is None or variable is None:
            return

        try:
            value = parse_value(type_id=variable.type_id, text=text)
            run_transaction(
                document=self.document,
                label=translate("Franky", "Edit VarSet variable"),
                action=lambda: set_property_value(varset, variable.name, value),
            )
        except Exception as error:
            self._reset_text(row=row, column=1, text=self._property_value_text(varset, variable.name))
            App.Console.PrintError(f"Could not update variable '{variable.name}': {error}\n")
            return

        self._reset_text(row=row, column=1, text=self._property_value_text(varset, variable.name))

    def _change_tooltip(self, row: int, text: str) -> None:
        varset = self._selected_varset()
        variable = self._variable_at(row=row)
        if varset is None or variable is None or text == variable.tooltip:
            return

        try:
            run_transaction(
                document=self.document,
                label=translate("Franky", "Edit VarSet variable tooltip"),
                action=lambda: varset.setDocumentationOfProperty(variable.name, text),
            )
        except Exception as error:
            self._reset_text(row=row, column=3, text=variable.tooltip)
            App.Console.PrintError(f"Could not update tooltip for '{variable.name}': {error}\n")
            return

        variable.tooltip = text

    def _type_changed(self, row: int, type_id: str) -> None:
        if self.loading:
            return

        varset = self._selected_varset()
        variable = self._variable_at(row=row)
        if varset is None or variable is None or type_id == variable.type_id:
            return

        value_text = self._item_text(row=row, column=1)
        tooltip = self._item_text(row=row, column=3)

        try:
            value = parse_value(type_id=type_id, text=value_text)
        except Exception as error:
            self._reset_type(row=row, type_id=variable.type_id)
            App.Console.PrintError(f"Could not convert '{variable.name}' to {type_id}: {error}\n")
            return

        old_type_id = variable.type_id
        old_value = varset.getPropertyByName(variable.name)

        def change_type() -> None:
            varset.removeProperty(variable.name)
            varset.addProperty(type_id, variable.name, VARIABLE_GROUP, tooltip)
            set_property_value(varset, variable.name, value)

        try:
            run_transaction(
                document=self.document,
                label=translate("Franky", "Change VarSet variable type"),
                action=change_type,
            )
        except Exception as error:
            self._reset_type(row=row, type_id=old_type_id)
            self._restore_property(varset=varset, variable=variable, old_type_id=old_type_id, old_value=old_value)
            App.Console.PrintError(f"Could not change type for '{variable.name}': {error}\n")
            return

        variable.type_id = type_id
        variable.tooltip = tooltip
        self._reset_text(row=row, column=1, text=self._property_value_text(varset, variable.name))
        self._resize_to_contents()

    def _restore_property(self, varset: Any, variable: VariableInfo, old_type_id: str, old_value: Any) -> None:
        if variable.name in getattr(varset, "PropertiesList", []):
            return

        try:
            varset.addProperty(old_type_id, variable.name, VARIABLE_GROUP, variable.tooltip)
            set_property_value(varset, variable.name, old_value)
        except Exception as error:
            App.Console.PrintError(f"Could not restore variable '{variable.name}': {error}\n")

    def _variable_at(self, row: int) -> VariableInfo | None:
        if row < 0 or row >= len(self.variables):
            return None

        return self.variables[row]

    def _item_text(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        return "" if item is None else item.text()

    def _reset_text(self, row: int, column: int, text: str) -> None:
        self.loading = True
        item = self.table.item(row, column)
        if item is not None:
            item.setText(text)
        self.loading = False

    def _reset_type(self, row: int, type_id: str) -> None:
        combo = self.table.cellWidget(row, 2)
        if not isinstance(combo, QtWidgets.QComboBox):
            return

        self.loading = True
        combo.setCurrentText(type_id)
        self.loading = False

    def _resize_to_contents(self) -> None:
        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()

        for column, minimum_width in enumerate(COLUMN_MINIMUM_WIDTHS):
            self.table.setColumnWidth(column, max(self.table.columnWidth(column), minimum_width))

        header = self.table.horizontalHeader()
        table_width = sum(self.table.columnWidth(column) for column in range(self.table.columnCount()))
        table_width += self.table.frameWidth() * 2 + COLUMN_PADDING

        row_count = self.table.rowCount()
        table_height = header.height() + self.table.frameWidth() * 2
        if row_count:
            table_height += sum(self.table.rowHeight(row) for row in range(row_count))
        else:
            table_height += self.table.verticalHeader().defaultSectionSize()

        self.table.setMinimumWidth(table_width)
        self.table.setMinimumHeight(table_height)

        desired_width = max(table_width + 36, self.sizeHint().width())
        desired_height = max(table_height + self.varset_combo.sizeHint().height() + 72, self.sizeHint().height())

        app = QtWidgets.QApplication.instance()
        screen = app.primaryScreen() if app is not None else None
        if screen is not None:
            available = screen.availableGeometry()
            desired_width = min(desired_width, round(available.width() * MAX_SCREEN_RATIO))
            desired_height = min(desired_height, round(available.height() * MAX_SCREEN_RATIO))

        self.resize(desired_width, desired_height)

    def _varset_label(self, varset: Any) -> str:
        name = str(getattr(varset, "Name", ""))
        label = str(getattr(varset, "Label", "") or name)
        if label == name:
            return label

        return f"{label} ({name})"


class VarSetQuickEditCommand:
    """Open the VarSet quick edit dialog."""

    Name: ClassVar[str] = "Franky_VarSetQuickEdit"
    Dialog: ClassVar[VarSetQuickEditDialog | None] = None

    def GetResources(self) -> dict[str, str]:
        return {
            "Pixmap": Resources.icon(path="brackets.svg"),
            "MenuText": translate(
                "Franky",
                "VarSet Quick Edit",
            ),
            "ToolTip": translate(
                "Franky",
                "Quickly edit variable sets",
            ),
        }

    def Activated(self) -> None:
        doc = App.ActiveDocument
        if doc is None or Gui.ActiveDocument is None:
            App.Console.PrintError("No active document.\n")
            return

        if not find_varsets(document=doc):
            App.Console.PrintError("No variable sets found in the active document.\n")
            return

        parent = Gui.getMainWindow() if hasattr(Gui, "getMainWindow") else None
        dialog = type(self).Dialog
        if dialog is None:
            dialog = VarSetQuickEditDialog(document=doc, parent=parent)
            type(self).Dialog = dialog
        else:
            dialog.refresh(document=doc)

        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def IsActive(self) -> bool:
        return bool(App.ActiveDocument and Gui.ActiveDocument)

    @classmethod
    def Install(cls) -> None:
        if App.GuiUp:
            App.Gui.addCommand(cls.Name, cls())
