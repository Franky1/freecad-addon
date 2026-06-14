# SPDX-License-Identifier: LGPL-2.1-or-later

"""Command to quickly edit variable sets in a more user-friendly way than the default FreeCAD interface."""

import keyword
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, ClassVar

import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

import FreeCAD as App

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
DEFAULT_NEW_VARIABLE_TYPE: str = "App::PropertyLength"
GROUP_COLUMN: int = 0
LABEL_COLUMN: int = 1
VALUE_COLUMN: int = 2
EXPRESSION_COLUMN: int = 3
TYPE_COLUMN: int = 4
TOOLTIP_COLUMN: int = 5
DELETE_COLUMN: int = 6
COLUMN_MINIMUM_WIDTHS: tuple[int, int, int, int, int, int, int] = (100, 160, 80, 240, 180, 240, 48)
EXPRESSION_VALUE_COLOR_RGB: tuple[int, int, int] = (255, 165, 0)  # orange
EXPRESSION_ERROR_COLOR_RGB: tuple[int, int, int] = (255, 80, 80)  # red, for expressions that fail to resolve
DELETE_BUTTON_STYLE: str = "QToolButton { color: #ff0000; }"
DIALOG_PADDING: int = 16
LAYOUT_SPACING: int = 10
TABLE_PADDING: int = 12
MAX_SCREEN_RATIO: float = 0.85

# Built-in FreeCAD expression functions, offered as completions (the trailing "(" is inserted too).
EXPRESSION_FUNCTIONS: tuple[str, ...] = (
    "abs(",
    "acos(",
    "asin(",
    "atan(",
    "atan2(",
    "ceil(",
    "cos(",
    "cosh(",
    "exp(",
    "floor(",
    "hypot(",
    "log(",
    "log10(",
    "max(",
    "min(",
    "mod(",
    "pow(",
    "round(",
    "sin(",
    "sinh(",
    "sqrt(",
    "tan(",
    "tanh(",
    "trunc(",
)
# Trailing token under the cursor: an identifier or a closed ``<<Label>>`` group, optionally followed by
# ``.member`` parts, or an unfinished ``<<Label`` reference still being typed.
EXPRESSION_TOKEN_RE: re.Pattern[str] = re.compile(r"(?:(?:<<[^<>]*>>|[A-Za-z_]\w*)(?:\.\w*)*|<<[^<>]*)$")


@dataclass
class VariableInfo:
    """Editable VarSet property metadata."""

    name: str
    type_id: str
    group: str
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
                group=get_property_text(varset, "getGroupOfProperty", property_name),
                tooltip=get_property_text(varset, "getDocumentationOfProperty", property_name),
            )
        )

    return variables


def stringify_value(value: Any) -> str:
    """Return a stable editable string for a FreeCAD property value."""
    if value is None:
        return ""

    return str(value)


def stringify_expression(expression: Any) -> str:
    """Return readable expression text from FreeCAD expression objects."""
    if expression is None:
        return ""

    to_string = getattr(expression, "toString", None)
    if callable(to_string):
        try:
            text = to_string()
        except Exception:
            text = None

        if text is not None:
            expression_text = str(text).strip()
            if expression_text and expression_text != "None":
                return expression_text

    expression_text = str(expression).strip()
    if not expression_text or expression_text == "None":
        return ""

    return expression_text


def expression_path_matches_property(path: Any, property_name: str) -> bool:
    """Return whether an ExpressionEngine path targets the given direct property."""
    path_text = str(path).strip()
    return path_text == property_name or path_text.endswith(f".{property_name}")


def get_property_expression(obj: Any, property_name: str) -> str:
    """Return the expression that calculates a property, if FreeCAD exposes one."""
    get_expression = getattr(obj, "getExpression", None)
    if callable(get_expression):
        try:
            expression = get_expression(property_name)
        except Exception:
            expression = None

        expression_text = stringify_expression(expression)
        if expression_text:
            return expression_text

    try:
        expression_engine = getattr(obj, "ExpressionEngine", [])
    except Exception:
        return ""

    try:
        entries = list(expression_engine or [])
    except TypeError:
        return ""

    for entry in entries:
        if not isinstance(entry, list | tuple) or len(entry) < 2:
            continue

        if expression_path_matches_property(path=entry[0], property_name=property_name):
            return stringify_expression(entry[1])

    return ""


def expression_resolves(obj: Any, expression: str) -> bool:
    """Return whether FreeCAD can evaluate the expression in the object's context."""
    expression_text = expression.strip()
    if not expression_text:
        return True

    eval_expression = getattr(obj, "evalExpression", None)
    if not callable(eval_expression):
        return True

    try:
        eval_expression(expression_text)
    except Exception:
        return False

    return True


def set_property_expression(obj: Any, property_name: str, expression: str) -> None:
    """Set or clear a FreeCAD expression on a property."""
    set_expression = getattr(obj, "setExpression", None)
    if not callable(set_expression):
        msg = "This variable set does not support expressions."
        raise RuntimeError(msg)

    expression_text = expression.strip()
    if expression_text:
        set_expression(property_name, expression_text)
        return

    try:
        set_expression(property_name, None)
    except TypeError:
        set_expression(property_name, "")


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


class ExpressionLineEdit(QtWidgets.QLineEdit):
    """Line edit that completes existing project variables, objects and functions while editing."""

    def __init__(self, context: dict[str, Any], parent: Any = None) -> None:
        super().__init__(parent)
        self._context = context
        self._current_prefix = ""

        self._model = QtCore.QStringListModel(self)
        self._completer = QtWidgets.QCompleter(self)
        self._completer.setModel(self._model)
        self._completer.setWidget(self)
        self._completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self._completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        self._completer.activated[str].connect(self._insert_completion)

        self.textEdited.connect(self._update_completions)

    def keyPressEvent(self, event: Any) -> None:
        if self._completer.popup().isVisible() and event.key() in (
            QtCore.Qt.Key_Enter,
            QtCore.Qt.Key_Return,
            QtCore.Qt.Key_Escape,
            QtCore.Qt.Key_Tab,
            QtCore.Qt.Key_Backtab,
        ):
            # Let the completer's event filter handle navigation/acceptance instead of the cell editor.
            event.ignore()
            return

        super().keyPressEvent(event)

    def _update_completions(self, _text: str = "") -> None:
        token = self._token_under_cursor()
        if not token:
            self._completer.popup().hide()
            return

        mode, base, prefix = self._classify(token)
        candidates = self._candidates(mode=mode, base=base)
        self._current_prefix = prefix

        self._model.setStringList(candidates)
        self._completer.setCompletionPrefix(prefix)
        if self._completer.completionCount() == 0:
            self._completer.popup().hide()
            return

        popup = self._completer.popup()
        popup.setCurrentIndex(self._completer.completionModel().index(0, 0))
        self._completer.complete()

    def _token_under_cursor(self) -> str:
        text_before_cursor = self.text()[: self.cursorPosition()]
        match = EXPRESSION_TOKEN_RE.search(text_before_cursor)
        return match.group(0) if match else ""

    def _classify(self, token: str) -> tuple[str, str | None, str]:
        if token.startswith("<<") and ">>" not in token:
            return "label", None, token

        if "." in token:
            base, _, partial = token.rpartition(".")
            return "property", base, partial

        return "top", None, token

    def _candidates(self, mode: str, base: str | None) -> list[str]:
        if mode == "label":
            return self._context["labels"]

        if mode == "property":
            return self._context["props"].get(base, [])

        return self._context["top"]

    def _insert_completion(self, completion: str) -> None:
        cursor = self.cursorPosition()
        text = self.text()
        start = cursor - len(self._current_prefix)
        self.setText(text[:start] + completion + text[cursor:])
        self.setCursorPosition(start + len(completion))
        self._completer.popup().hide()


class ExpressionCompletionDelegate(QtWidgets.QStyledItemDelegate):
    """Cell delegate that edits the Expression column with a variable-aware autocompleting line edit."""

    def __init__(self, dialog: "VarSetQuickEditDialog", parent: Any = None) -> None:
        super().__init__(parent)
        self.dialog = dialog

    def createEditor(self, parent: Any, option: Any, index: Any) -> Any:
        return ExpressionLineEdit(context=self.dialog.expression_context(), parent=parent)

    def setEditorData(self, editor: Any, index: Any) -> None:
        editor.setText(str(index.data(QtCore.Qt.EditRole) or ""))

    def setModelData(self, editor: Any, model: Any, index: Any) -> None:
        model.setData(index, editor.text(), QtCore.Qt.EditRole)


class VarSetQuickEditDialog(QtWidgets.QDialog):
    """Dialog for editing variables from document variable sets."""

    def __init__(self, document: Any, parent: Any = None) -> None:
        super().__init__(parent)
        self.document: Any = document
        self.varsets: dict[str, Any] = {}
        self.variables: list[VariableInfo] = []
        self.loading: bool = False
        self.adding_variable: bool = False
        self.reload_pending: bool = False

        self.setWindowTitle(translate("Franky", "VarSet Quick Editor"))
        self.setWindowIcon(QtGui.QIcon(Resources.icon(path="brackets.svg")))
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)

        self.varset_combo = QtWidgets.QComboBox(parent=self)
        self.varset_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.varset_combo.currentIndexChanged.connect(self._selected_varset_changed)

        self.table = QtWidgets.QTableWidget(parent=self)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                translate("Franky", "Group"),
                translate("Franky", "Label"),
                translate("Franky", "VarSet Value"),
                translate("Franky", "Expression"),
                translate("Franky", "Type"),
                translate("Franky", "Tooltip"),
                translate("Franky", "Delete"),
            ]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setDefaultAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        self.table.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.table.itemChanged.connect(self._item_changed)
        self.table.setItemDelegateForColumn(
            EXPRESSION_COLUMN, ExpressionCompletionDelegate(dialog=self, parent=self.table)
        )

        selector_layout = QtWidgets.QHBoxLayout()
        selector_layout.setContentsMargins(0, 0, 0, 0)
        selector_layout.setSpacing(LAYOUT_SPACING)
        selector_layout.addWidget(QtWidgets.QLabel(translate("Franky", "VarSet"), parent=self))
        selector_layout.addWidget(self.varset_combo, 1)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(DIALOG_PADDING, DIALOG_PADDING, DIALOG_PADDING, DIALOG_PADDING)
        layout.setSpacing(LAYOUT_SPACING)
        layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
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

    def expression_context(self) -> dict[str, Any]:
        """Build the completion data offered while editing an expression.

        Returns a mapping with ``top`` (identifiers usable at the start of a token: the current
        VarSet's variables, object names and functions), ``labels`` (``<<Label>>`` references for
        every document object) and ``props`` (property names keyed by both object name and
        ``<<Label>>`` reference, used after a ``.``).
        """
        object_names: list[str] = []
        labels: list[str] = []
        props: dict[str, list[str]] = {}

        for obj in getattr(self.document, "Objects", []):
            name = str(getattr(obj, "Name", ""))
            if not name:
                continue

            label = str(getattr(obj, "Label", "") or name)
            property_names = [str(property_name) for property_name in getattr(obj, "PropertiesList", [])]

            object_names.append(name)
            labels.append(f"<<{label}>>")
            props[name] = property_names
            props[f"<<{label}>>"] = property_names

        variable_names = [variable.name for variable in self.variables]
        top = list(dict.fromkeys([*variable_names, *object_names, *EXPRESSION_FUNCTIONS]))

        return {"top": top, "labels": labels, "props": props}

    @contextmanager
    def _table_update(self) -> Iterator[None]:
        previous_loading = self.loading
        previous_blocked = self.table.blockSignals(True)
        self.loading = True
        try:
            yield
        finally:
            self.loading = previous_loading
            self.table.blockSignals(previous_blocked)

    def _load_selected_varset(self) -> None:
        with self._table_update():
            self.variables = []
            self.table.setRowCount(0)

            varset = self._selected_varset()
            if varset is not None:
                self.variables = list_variables(varset=varset)
                self.table.setRowCount(len(self.variables) + 1)
                for row, variable in enumerate(self.variables):
                    expression = get_property_expression(obj=varset, property_name=variable.name)
                    self._set_text_item(row=row, column=GROUP_COLUMN, text=variable.group)
                    self._set_text_item(row=row, column=LABEL_COLUMN, text=variable.name)
                    self._set_value_item(
                        row=row, text=self._property_value_text(varset, variable.name), expression=expression
                    )
                    self._set_expression_item(row=row, varset=varset, expression=expression)
                    self._set_type_combo(row=row, variable=variable)
                    self._set_text_item(row=row, column=TOOLTIP_COLUMN, text=variable.tooltip)
                    self._set_delete_button(row=row, variable=variable)

                self._set_new_variable_row(row=len(self.variables))

        self._resize_to_contents()

    def _load_selected_varset_later(self) -> None:
        if self.reload_pending:
            return

        self.reload_pending = True
        QtCore.QTimer.singleShot(0, self._load_pending_selected_varset)

    def _load_pending_selected_varset(self) -> None:
        self.reload_pending = False
        self._load_selected_varset()

    def _set_text_item(self, row: int, column: int, text: str, editable: bool = True) -> None:
        item = QtWidgets.QTableWidgetItem(text)
        self._set_item_editable(item=item, editable=editable)
        self.table.setItem(row, column, item)

    def _set_item_editable(self, item: Any, editable: bool) -> None:
        if editable:
            item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
        else:
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)

    def _set_value_editable(self, row: int, editable: bool) -> None:
        with self._table_update():
            item = self.table.item(row, VALUE_COLUMN)
            if item is not None:
                self._set_item_editable(item=item, editable=editable)

    def _set_value_item(self, row: int, text: str, expression: str) -> None:
        self._set_text_item(row=row, column=VALUE_COLUMN, text=text, editable=not expression)
        item = self.table.item(row, VALUE_COLUMN)
        if item is None or not expression:
            return

        item.setForeground(QtGui.QColor(*EXPRESSION_VALUE_COLOR_RGB))
        item.setToolTip(translate("Franky", "Calculated by expression"))

    def _set_expression_item(self, row: int, varset: Any, expression: str) -> None:
        self._set_text_item(row=row, column=EXPRESSION_COLUMN, text=expression)
        item = self.table.item(row, EXPRESSION_COLUMN)
        if item is None or not expression:
            return

        if not expression_resolves(obj=varset, expression=expression):
            item.setForeground(QtGui.QColor(*EXPRESSION_ERROR_COLOR_RGB))
            item.setToolTip(translate("Franky", "Expression could not be resolved"))

    def _reset_value_and_expression(self, row: int, varset: Any, variable: VariableInfo) -> None:
        value_text = self._property_value_text(varset, variable.name)
        expression = get_property_expression(obj=varset, property_name=variable.name)

        with self._table_update():
            self._set_value_item(row=row, text=value_text, expression=expression)
            self._set_expression_item(row=row, varset=varset, expression=expression)

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
        self.table.setCellWidget(row, TYPE_COLUMN, combo)

    def _set_delete_button(self, row: int, variable: VariableInfo) -> None:
        button = QtWidgets.QToolButton(parent=self.table)
        button.setText("X")
        button.setStyleSheet(DELETE_BUTTON_STYLE)
        button.setToolTip(translate("Franky", "Delete variable"))
        button.clicked.connect(lambda _checked=False, name=variable.name: self._delete_variable(name))
        self.table.setCellWidget(row, DELETE_COLUMN, button)

    def _set_new_variable_row(self, row: int) -> None:
        self._set_text_item(row=row, column=GROUP_COLUMN, text=self._new_variable_group())
        self._set_text_item(row=row, column=LABEL_COLUMN, text="")
        self._set_text_item(row=row, column=VALUE_COLUMN, text="")
        self._set_text_item(row=row, column=EXPRESSION_COLUMN, text="")
        variable = VariableInfo(
            name="",
            type_id=DEFAULT_NEW_VARIABLE_TYPE,
            group=self._new_variable_group(),
            tooltip="",
        )
        self._set_type_combo(
            row=row,
            variable=variable,
        )
        self._set_text_item(row=row, column=TOOLTIP_COLUMN, text="")
        self._set_text_item(row=row, column=DELETE_COLUMN, text="", editable=False)

    def _new_variable_group(self) -> str:
        if not self.variables:
            return VARIABLE_GROUP

        return self.variables[-1].group

    def _property_value_text(self, varset: Any, property_name: str) -> str:
        try:
            return stringify_value(varset.getPropertyByName(property_name))
        except Exception:
            return ""

    def _add_property_with_state(
        self,
        varset: Any,
        name: str,
        type_id: str,
        group: str,
        tooltip: str,
        value: Any,
        expression: str,
    ) -> None:
        varset.addProperty(type_id, name, group, tooltip)
        set_property_value(varset, name, value)
        if expression:
            set_property_expression(varset, name, expression)

    def _replace_property_with_state(
        self,
        varset: Any,
        name: str,
        type_id: str,
        group: str,
        tooltip: str,
        value: Any,
        expression: str,
    ) -> None:
        varset.removeProperty(name)
        self._add_property_with_state(
            varset=varset,
            name=name,
            type_id=type_id,
            group=group,
            tooltip=tooltip,
            value=value,
            expression=expression,
        )

    def _item_changed(self, item: Any) -> None:
        if self.loading or self.adding_variable:
            return

        row = int(item.row())
        column = int(item.column())
        if self._is_new_variable_row(row=row):
            self._set_value_editable(row=row, editable=not self._item_text(row=row, column=EXPRESSION_COLUMN).strip())
            self._add_variable_from_new_row(row=row)
            self._resize_to_contents()
            return

        if column == GROUP_COLUMN:
            self._change_group(row=row, new_group=item.text().strip())
        elif column == LABEL_COLUMN:
            self._rename_variable(row=row, new_name=item.text().strip())
        elif column == VALUE_COLUMN:
            self._change_value(row=row, text=item.text())
        elif column == EXPRESSION_COLUMN:
            self._change_expression(row=row, expression=item.text())
        elif column == TOOLTIP_COLUMN:
            self._change_tooltip(row=row, text=item.text())

        self._resize_to_contents()

    def _add_variable_from_new_row(self, row: int) -> None:
        if self.adding_variable:
            return

        self.adding_variable = True
        try:
            self._add_variable_from_new_row_guarded(row=row)
        finally:
            self.adding_variable = False

    def _add_variable_from_new_row_guarded(self, row: int) -> None:
        varset = self._selected_varset()
        if varset is None:
            return

        name = self._item_text(row=row, column=LABEL_COLUMN).strip()
        if not name:
            return

        if not validate_property_name(name):
            self._reset_text(row=row, column=LABEL_COLUMN, text="")
            App.Console.PrintError("Variable names must be valid Python-style identifiers.\n")
            return

        if name in getattr(varset, "PropertiesList", []):
            self._reset_text(row=row, column=LABEL_COLUMN, text="")
            App.Console.PrintError(f"Variable '{name}' already exists.\n")
            return

        type_id = self._type_text(row=row)
        group = self._item_text(row=row, column=GROUP_COLUMN).strip()
        value_text = self._item_text(row=row, column=VALUE_COLUMN)
        expression = self._item_text(row=row, column=EXPRESSION_COLUMN).strip()
        tooltip = self._item_text(row=row, column=TOOLTIP_COLUMN)

        try:
            value = parse_value(type_id=type_id, text=value_text)
        except Exception as error:
            App.Console.PrintError(f"Could not create variable '{name}': {error}\n")
            return

        def add_variable() -> None:
            self._add_property_with_state(
                varset=varset,
                name=name,
                type_id=type_id,
                group=group,
                tooltip=tooltip,
                value=value,
                expression=expression,
            )

        try:
            run_transaction(
                document=self.document,
                label=translate("Franky", "Add VarSet variable"),
                action=add_variable,
            )
        except Exception as error:
            App.Console.PrintError(f"Could not create variable '{name}': {error}\n")
            return

        self._load_selected_varset_later()

    def _delete_variable(self, variable_name: str) -> None:
        if self.loading or self.adding_variable:
            return

        varset = self._selected_varset()
        if varset is None:
            return

        if variable_name not in getattr(varset, "PropertiesList", []):
            App.Console.PrintError(f"Variable '{variable_name}' no longer exists.\n")
            self._load_selected_varset()
            return

        try:
            run_transaction(
                document=self.document,
                label=translate("Franky", "Delete VarSet variable"),
                action=lambda: varset.removeProperty(variable_name),
            )
        except Exception as error:
            App.Console.PrintError(f"Could not delete variable '{variable_name}': {error}\n")
            return

        self._load_selected_varset()

    def _change_group(self, row: int, new_group: str) -> None:
        varset = self._selected_varset()
        variable = self._variable_at(row=row)
        if varset is None or variable is None or new_group == variable.group:
            return

        old_group = variable.group
        old_value = varset.getPropertyByName(variable.name)
        old_expression = get_property_expression(obj=varset, property_name=variable.name)
        tooltip = self._item_text(row=row, column=TOOLTIP_COLUMN)

        def change_group() -> None:
            self._replace_property_with_state(
                varset=varset,
                name=variable.name,
                type_id=variable.type_id,
                group=new_group,
                tooltip=tooltip,
                value=old_value,
                expression=old_expression,
            )

        try:
            run_transaction(
                document=self.document,
                label=translate("Franky", "Edit VarSet variable group"),
                action=change_group,
            )
        except Exception as error:
            self._reset_text(row=row, column=GROUP_COLUMN, text=old_group)
            self._restore_property(
                varset=varset,
                variable=variable,
                type_id=variable.type_id,
                group=old_group,
                tooltip=variable.tooltip,
                value=old_value,
                expression=old_expression,
            )
            App.Console.PrintError(f"Could not update group for '{variable.name}': {error}\n")
            return

        variable.group = new_group
        variable.tooltip = tooltip
        self._reset_value_and_expression(row=row, varset=varset, variable=variable)

    def _rename_variable(self, row: int, new_name: str) -> None:
        varset = self._selected_varset()
        variable = self._variable_at(row=row)
        if varset is None or variable is None or new_name == variable.name:
            return

        if not validate_property_name(new_name):
            self._reset_text(row=row, column=LABEL_COLUMN, text=variable.name)
            App.Console.PrintError("Variable names must be valid Python-style identifiers.\n")
            return

        if new_name in getattr(varset, "PropertiesList", []):
            self._reset_text(row=row, column=LABEL_COLUMN, text=variable.name)
            App.Console.PrintError(f"Variable '{new_name}' already exists.\n")
            return

        try:
            run_transaction(
                document=self.document,
                label=translate("Franky", "Rename VarSet variable"),
                action=lambda: varset.renameProperty(variable.name, new_name),
            )
        except Exception as error:
            self._reset_text(row=row, column=LABEL_COLUMN, text=variable.name)
            App.Console.PrintError(f"Could not rename variable '{variable.name}': {error}\n")
            return

        variable.name = new_name

    def _change_value(self, row: int, text: str) -> None:
        varset = self._selected_varset()
        variable = self._variable_at(row=row)
        if varset is None or variable is None:
            return

        if get_property_expression(obj=varset, property_name=variable.name):
            self._reset_value_and_expression(row=row, varset=varset, variable=variable)
            App.Console.PrintError(f"Clear the expression before editing the value for '{variable.name}'.\n")
            return

        try:
            value = parse_value(type_id=variable.type_id, text=text)
            run_transaction(
                document=self.document,
                label=translate("Franky", "Edit VarSet variable"),
                action=lambda: set_property_value(varset, variable.name, value),
            )
        except Exception as error:
            self._reset_value_and_expression(row=row, varset=varset, variable=variable)
            App.Console.PrintError(f"Could not update variable '{variable.name}': {error}\n")
            return

        self._reset_value_and_expression(row=row, varset=varset, variable=variable)

    def _change_expression(self, row: int, expression: str) -> None:
        varset = self._selected_varset()
        variable = self._variable_at(row=row)
        if varset is None or variable is None:
            return

        expression_text = expression.strip()
        old_expression = get_property_expression(obj=varset, property_name=variable.name)
        if expression_text == old_expression:
            self._reset_value_and_expression(row=row, varset=varset, variable=variable)
            return

        try:
            run_transaction(
                document=self.document,
                label=translate("Franky", "Edit VarSet variable expression"),
                action=lambda: set_property_expression(varset, variable.name, expression_text),
            )
        except Exception as error:
            self._reset_value_and_expression(row=row, varset=varset, variable=variable)
            App.Console.PrintError(f"Could not update expression for '{variable.name}': {error}\n")
            return

        self._reset_value_and_expression(row=row, varset=varset, variable=variable)

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
            self._reset_text(row=row, column=TOOLTIP_COLUMN, text=variable.tooltip)
            App.Console.PrintError(f"Could not update tooltip for '{variable.name}': {error}\n")
            return

        variable.tooltip = text

    def _type_changed(self, row: int, type_id: str) -> None:
        if self.loading or self.adding_variable:
            return

        varset = self._selected_varset()
        if self._is_new_variable_row(row=row):
            self._add_variable_from_new_row(row=row)
            return

        variable = self._variable_at(row=row)
        if varset is None or variable is None or type_id == variable.type_id:
            return

        value_text = self._item_text(row=row, column=VALUE_COLUMN)
        tooltip = self._item_text(row=row, column=TOOLTIP_COLUMN)

        try:
            value = parse_value(type_id=type_id, text=value_text)
        except Exception as error:
            self._reset_type(row=row, type_id=variable.type_id)
            App.Console.PrintError(f"Could not convert '{variable.name}' to {type_id}: {error}\n")
            return

        old_type_id = variable.type_id
        old_value = varset.getPropertyByName(variable.name)
        old_expression = get_property_expression(obj=varset, property_name=variable.name)

        def change_type() -> None:
            self._replace_property_with_state(
                varset=varset,
                name=variable.name,
                type_id=type_id,
                group=variable.group,
                tooltip=tooltip,
                value=value,
                expression=old_expression,
            )

        try:
            run_transaction(
                document=self.document,
                label=translate("Franky", "Change VarSet variable type"),
                action=change_type,
            )
        except Exception as error:
            self._reset_type(row=row, type_id=old_type_id)
            self._restore_property(
                varset=varset,
                variable=variable,
                type_id=old_type_id,
                group=variable.group,
                tooltip=variable.tooltip,
                value=old_value,
                expression=old_expression,
            )
            App.Console.PrintError(f"Could not change type for '{variable.name}': {error}\n")
            return

        variable.type_id = type_id
        variable.tooltip = tooltip
        self._reset_value_and_expression(row=row, varset=varset, variable=variable)
        self._resize_to_contents()

    def _restore_property(
        self,
        varset: Any,
        variable: VariableInfo,
        type_id: str,
        group: str,
        tooltip: str,
        value: Any,
        expression: str,
    ) -> None:
        if variable.name in getattr(varset, "PropertiesList", []):
            return

        try:
            self._add_property_with_state(
                varset=varset,
                name=variable.name,
                type_id=type_id,
                group=group,
                tooltip=tooltip,
                value=value,
                expression=expression,
            )
        except Exception as error:
            App.Console.PrintError(f"Could not restore variable '{variable.name}': {error}\n")

    def _variable_at(self, row: int) -> VariableInfo | None:
        if row < 0 or row >= len(self.variables):
            return None

        return self.variables[row]

    def _is_new_variable_row(self, row: int) -> bool:
        return bool(self.varsets) and row == len(self.variables)

    def _item_text(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        return "" if item is None else item.text()

    def _type_text(self, row: int) -> str:
        combo = self.table.cellWidget(row, TYPE_COLUMN)
        if isinstance(combo, QtWidgets.QComboBox):
            return str(combo.currentText())

        return DEFAULT_NEW_VARIABLE_TYPE

    def _reset_text(self, row: int, column: int, text: str) -> None:
        with self._table_update():
            item = self.table.item(row, column)
            if item is not None:
                item.setText(text)

    def _reset_type(self, row: int, type_id: str) -> None:
        combo = self.table.cellWidget(row, TYPE_COLUMN)
        if not isinstance(combo, QtWidgets.QComboBox):
            return

        previous_loading = self.loading
        previous_blocked = combo.blockSignals(True)
        self.loading = True
        try:
            combo.setCurrentText(type_id)
        finally:
            self.loading = previous_loading
            combo.blockSignals(previous_blocked)

    def _resize_to_contents(self) -> None:
        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()

        for column, minimum_width in enumerate(COLUMN_MINIMUM_WIDTHS):
            self.table.setColumnWidth(column, max(self.table.columnWidth(column), minimum_width))

        header = self.table.horizontalHeader()
        table_width = sum(self.table.columnWidth(column) for column in range(self.table.columnCount()))
        table_width += self.table.frameWidth() * 2 + TABLE_PADDING

        row_count = self.table.rowCount()
        table_height = header.height() + self.table.frameWidth() * 2
        if row_count:
            table_height += sum(self.table.rowHeight(row) for row in range(row_count))
        else:
            table_height += self.table.verticalHeader().defaultSectionSize()

        app = QtWidgets.QApplication.instance()
        screen = app.primaryScreen() if app is not None else None
        if screen is not None:
            available = screen.availableGeometry()
            maximum_width = round(available.width() * MAX_SCREEN_RATIO) - (DIALOG_PADDING * 2)
            maximum_height = round(available.height() * MAX_SCREEN_RATIO) - (
                self.varset_combo.sizeHint().height() + DIALOG_PADDING * 2 + LAYOUT_SPACING
            )

            scrollbar_size = self.table.style().pixelMetric(QtWidgets.QStyle.PM_ScrollBarExtent)
            needs_vertical_scrollbar = table_height > maximum_height
            if needs_vertical_scrollbar:
                table_width += scrollbar_size

            needs_horizontal_scrollbar = table_width > maximum_width
            if needs_horizontal_scrollbar:
                table_height += scrollbar_size

            if not needs_vertical_scrollbar and table_height > maximum_height:
                table_width += scrollbar_size

            table_width = min(table_width, maximum_width)
            table_height = min(table_height, maximum_height)

        self.table.setFixedSize(table_width, table_height)
        self.adjustSize()

    def _varset_label(self, varset: Any) -> str:
        name = str(getattr(varset, "Name", ""))
        label = str(getattr(varset, "Label", "") or name)
        if label == name:
            return label

        return f"{label} ({name})"


class VarSetQuickEditCommand:
    """Open the VarSet Quick Editor dialog."""

    Name: ClassVar[str] = "Franky_VarSetQuickEdit"
    Dialog: ClassVar[VarSetQuickEditDialog | None] = None

    def GetResources(self) -> dict[str, str]:
        return {
            "Pixmap": Resources.icon(path="brackets.svg"),
            "MenuText": translate(
                "Franky",
                "VarSet Quick Editor",
            ),
            "ToolTip": translate(
                "Franky",
                "Quickly edit Variable Sets",
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
