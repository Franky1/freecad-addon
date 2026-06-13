# SPDX-License-Identifier: LGPL-2.1-or-later

"""
Command to create a new FreeCAD project with a user-friendly PySide Widget, pre-configured for better workflow.
- Label at the top for a project name, creates new FreeCAD document and names .FCStd file accordingly.
- Default project structure is created in the project tree:
    - Creates a "00_Master" folder in the project tree.
        - Creates an empty "00_MasterSketch" sketch in the "00_Master" folder.
        - Creates an empty "vv" VarSet in the "00_Master" folder.
    - Widget has 10 input fields for the user to give names to Body folders, which are created in the project tree with the given names.
    - Widget has 5 columns behind the input fields, with
        - Color selector for the Body color.
        - Dropdown for "Sketch Plane" (None, XY, XZ, YZ). Default is None.
        - Dropdown for "Datum Plane" (None, XY, XZ, YZ). Default is None.
        - Dropdown for "Datum Line" (None, X, Y, Z). Default is None.
        - Checkbox for "Datum Point". Default is unchecked.
        - Description input field, which can be used by the user to write a description for each Body.
    - For each given Body name, create a subfolder starting with "XX_" to ensure it appears in the correct order in the project tree.
    - The "XX_" prefix is automatically added to the given name, starting with "01_" for the first Body, "02_" for the second, and so on, so the user only needs to give the name of the Body.
    - Within each Body folder, creates an empty Body, named "XX_Body_Name".
    - Within each Body folder, creates an empty sketch within the Body, named "XX_Sketch_Name", only when a sketch plane is selected.
    - Within each Body folder, creates an empty Datum Plane, named "XX_DatumPlane_Name", and places it on the selected "Datum Plane" if given.
    - Within each Body folder, creates an empty Datum Line, named "XX_DatumLine_Name", and places it on the selected "Datum Line" if given.
    - Within each Body folder, creates an empty Datum Point, named "XX_DatumPoint_Name", if selected.
    - Only creates as many Body folders as the user gives names for, so if the user only gives 3 names, only 3 Body folders are created.
- Widget has a "Create Project" button, which creates the project, saves it, and closes the widget.
- Widget has a "Cancel" button, which closes the widget without creating a project.
- Widget has a "Reset" button, which clears all input fields and resets the widget to its initial state.
- Save path is the default FreeCAD save path.

"""

import keyword
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, TypeAlias

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

translate = App.Qt.translate

from ..resources import Resources

BODY_ROW_COUNT: int = 10
DIALOG_PADDING: int = 16
LAYOUT_SPACING: int = 10
COLOR_SWATCH_WIDTH: int = 48
PROJECT_NAME_PLACEHOLDER: str = "MyProject"
MASTER_GROUP_LABEL: str = "00_Master"
MASTER_SKETCH_LABEL: str = "00_MasterSketch"
MASTER_VARSET_LABEL: str = "vv"
PLANE_CHOICES: tuple[str, ...] = ("None", "XY", "XZ", "YZ")
AXIS_CHOICES: tuple[str, ...] = ("None", "X", "Y", "Z")
BodyColor: TypeAlias = tuple[float, float, float]
DEFAULT_BODY_COLORS: tuple[BodyColor, ...] = (
    (0.80, 0.20, 0.18),
    (0.92, 0.50, 0.16),
    (0.95, 0.72, 0.20),
    (0.35, 0.66, 0.30),
    (0.18, 0.62, 0.64),
    (0.24, 0.44, 0.80),
    (0.48, 0.32, 0.72),
    (0.78, 0.34, 0.58),
    (0.46, 0.50, 0.55),
    (0.72, 0.48, 0.28),
)
WINDOWS_RESERVED_FILENAMES: frozenset[str] = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
)


@dataclass
class BodyTemplate:
    """User-entered body setup from the dialog."""

    index: int
    name: str
    color: BodyColor
    sketch_plane: str
    datum_plane: str
    datum_line: str
    create_datum_point: bool
    description: str

    @property
    def ordered_label(self) -> str:
        return f"{self.index:02d}_{self.name}"

    def object_label(self, object_type: str) -> str:
        return f"{self.index:02d}_{object_type}_{self.name}"


def default_save_path() -> Path:
    """Return FreeCAD's default save folder, falling back to the home folder."""
    parameters = App.ParamGet("User parameter:BaseApp/Preferences/General")
    configured_path = parameters.GetString("FileOpenSavePath", "")
    if configured_path:
        path = Path(configured_path).expanduser()
        if path.is_dir():
            return path

    return Path.home()


def is_safe_filename(name: str) -> bool:
    """Return whether the project name can safely be used as a Windows-first filename."""
    if not name:
        return False

    stripped = name.strip()
    if stripped != name or stripped.endswith("."):
        return False

    invalid_characters = '<>:"/\\|?*'
    if any(character in invalid_characters or ord(character) < 32 for character in stripped):
        return False

    return stripped.upper() not in WINDOWS_RESERVED_FILENAMES


def safe_object_name(label: str) -> str:
    """Convert a visible label to a stable FreeCAD object name."""
    name = "".join(character if character.isalnum() or character == "_" else "_" for character in label.strip())
    name = "_".join(part for part in name.split("_") if part)
    if not name or name[0].isdigit() or keyword.iskeyword(name):
        name = f"Franky_{name}"

    return name


def add_group(document: Any, label: str) -> Any:
    """Create a document group with a stable internal name and visible label."""
    group = document.addObject("App::DocumentObjectGroup", safe_object_name(label))
    group.Label = label
    return group


def add_to_group(group: Any, obj: Any) -> None:
    """Add an object to a FreeCAD group when the API is available."""
    add_object = getattr(group, "addObject", None)
    if callable(add_object):
        add_object(obj)


def add_body_object(body: Any, type_id: str, name: str, label: str) -> Any:
    """Create an object inside a PartDesign Body."""
    obj = body.newObject(type_id, safe_object_name(name))
    obj.Label = label
    return obj


def body_color_to_qcolor(color: BodyColor) -> Any:
    """Convert a FreeCAD color tuple to a Qt color."""
    return QtGui.QColor.fromRgbF(*color)


def qcolor_to_body_color(color: Any) -> BodyColor:
    """Convert a Qt color to a FreeCAD color tuple."""
    return (float(color.redF()), float(color.greenF()), float(color.blueF()))


def set_body_color(body: Any, color: BodyColor) -> None:
    """Set the display color of a PartDesign Body when the GUI view object is available."""
    if not App.GuiUp:
        return

    view_object = getattr(body, "ViewObject", None)
    if view_object is None:
        return

    try:
        view_object.ShapeColor = color
    except Exception:
        pass


def rename_body_origin(body: Any, label: str) -> None:
    """Rename the implicit PartDesign Body origin when FreeCAD exposes it."""
    origin = getattr(body, "Origin", None)
    if origin is None:
        return

    try:
        origin.Label = label
    except Exception:
        pass


def set_description(obj: Any, description: str) -> None:
    """Store a body description where FreeCAD exposes a description/editor property."""
    if not description:
        return

    for property_name in ("Description", "Label2"):
        if property_name not in getattr(obj, "PropertiesList", []):
            continue

        try:
            setattr(obj, property_name, description)
            return
        except Exception:
            pass


def origin_feature(body: Any, label: str) -> Any | None:
    """Find a standard origin plane or axis from a PartDesign body."""
    origin = getattr(body, "Origin", None)
    for feature in getattr(origin, "OriginFeatures", []) or []:
        feature_label = str(getattr(feature, "Label", ""))
        feature_name = str(getattr(feature, "Name", ""))
        if feature_label == label or feature_name == label:
            return feature

    return None


def set_placement(obj: Any, placement: Any) -> None:
    """Set placement on an object when supported."""
    try:
        obj.Placement = placement
    except Exception:
        pass


def plane_placement(plane: str) -> Any:
    """Return a placement for an object lying on a principal plane."""
    if plane == "XZ":
        return App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(1, 0, 0), 90))
    if plane == "YZ":
        return App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 1, 0), 90))

    return App.Placement(App.Vector(0, 0, 0), App.Rotation())


def axis_placement(axis: str) -> Any:
    """Return a placement for a datum line aligned with a principal axis."""
    if axis == "X":
        return App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 1, 0), 90))
    if axis == "Y":
        return App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(1, 0, 0), -90))

    return App.Placement(App.Vector(0, 0, 0), App.Rotation())


def attach_to_origin(obj: Any, support: Any, map_modes: tuple[str, ...]) -> bool:
    """Best-effort attachment to a body origin object."""
    if support is None:
        return False

    for support_value in ([(support, "")], [(support, ("",))], (support, [""])):
        try:
            obj.AttachmentSupport = support_value
            break
        except Exception:
            continue
    else:
        return False

    for map_mode in map_modes:
        try:
            obj.MapMode = map_mode
            return True
        except Exception:
            continue

    return False


def place_on_plane(obj: Any, body: Any, plane: str, map_modes: tuple[str, ...] = ("FlatFace", "ObjectXY")) -> None:
    """Place an object on the selected principal plane."""
    if plane == "None":
        return

    support = origin_feature(body=body, label=f"{plane}_Plane")
    if not attach_to_origin(obj=obj, support=support, map_modes=map_modes):
        set_placement(obj=obj, placement=plane_placement(plane=plane))


def place_on_axis(obj: Any, body: Any, axis: str) -> None:
    """Place a datum line on the selected principal axis."""
    if axis == "None":
        return

    support = origin_feature(body=body, label=f"{axis}_Axis")
    if not attach_to_origin(obj=obj, support=support, map_modes=("ObjectAxis", "ObjectZ")):
        set_placement(obj=obj, placement=axis_placement(axis=axis))


def create_master_objects(document: Any) -> None:
    """Create the default master group, sketch, and VarSet."""
    master_group = add_group(document=document, label=MASTER_GROUP_LABEL)

    sketch = document.addObject("Sketcher::SketchObject", safe_object_name(MASTER_SKETCH_LABEL))
    sketch.Label = MASTER_SKETCH_LABEL
    add_to_group(group=master_group, obj=sketch)

    varset = document.addObject("App::VarSet", safe_object_name(MASTER_VARSET_LABEL))
    varset.Label = MASTER_VARSET_LABEL
    add_to_group(group=master_group, obj=varset)


def create_body_objects(document: Any, template: BodyTemplate) -> None:
    """Create one ordered body group and its requested starter objects."""
    body_group = add_group(document=document, label=template.ordered_label)

    body_label = template.object_label(object_type="Body")
    body = document.addObject("PartDesign::Body", safe_object_name(body_label))
    body.Label = body_label
    set_body_color(body=body, color=template.color)
    rename_body_origin(body=body, label=template.object_label(object_type="Origin"))
    set_description(obj=body, description=template.description)
    add_to_group(group=body_group, obj=body)

    if template.sketch_plane != "None":
        sketch_label = template.object_label(object_type="Sketch")
        sketch = add_body_object(
            body=body,
            type_id="Sketcher::SketchObject",
            name=sketch_label,
            label=sketch_label,
        )
        set_description(obj=sketch, description=template.description)
        place_on_plane(obj=sketch, body=body, plane=template.sketch_plane)

    if template.datum_plane != "None":
        datum_plane_label = template.object_label(object_type="DatumPlane")
        datum_plane = add_body_object(
            body=body,
            type_id="PartDesign::Plane",
            name=datum_plane_label,
            label=datum_plane_label,
        )
        set_description(obj=datum_plane, description=template.description)
        place_on_plane(obj=datum_plane, body=body, plane=template.datum_plane)

    if template.datum_line != "None":
        datum_line_label = template.object_label(object_type="DatumLine")
        datum_line = add_body_object(
            body=body,
            type_id="PartDesign::Line",
            name=datum_line_label,
            label=datum_line_label,
        )
        set_description(obj=datum_line, description=template.description)
        place_on_axis(obj=datum_line, body=body, axis=template.datum_line)

    if template.create_datum_point:
        datum_point_label = template.object_label(object_type="DatumPoint")
        datum_point = add_body_object(
            body=body,
            type_id="PartDesign::Point",
            name=datum_point_label,
            label=datum_point_label,
        )
        set_description(obj=datum_point, description=template.description)


def create_project(project_name: str, body_templates: list[BodyTemplate]) -> None:
    """Create and save a new project document."""
    save_folder = default_save_path()
    file_path = save_folder / f"{project_name}.FCStd"
    if file_path.exists():
        msg = f"Project file already exists: {file_path}"
        raise FileExistsError(msg)

    document = App.newDocument(safe_object_name(project_name))
    document.Label = project_name
    document.openTransaction(translate("Franky", "Create Franky project"))
    transaction_open = True
    try:
        create_master_objects(document=document)
        for template in body_templates:
            create_body_objects(document=document, template=template)

        document.commitTransaction()
        transaction_open = False
        document.recompute()
        document.saveAs(str(file_path))
    except Exception:
        if transaction_open:
            document.abortTransaction()
        raise

    App.Console.PrintMessage(f"Created project {file_path}\n")


class BodyTemplateRow:
    """Input widgets for one body template row."""

    def __init__(self, parent: Any, index: int) -> None:
        self.index = index
        self.default_color = DEFAULT_BODY_COLORS[(index - 1) % len(DEFAULT_BODY_COLORS)]
        self.name_edit = QtWidgets.QLineEdit(parent=parent)
        self.name_edit.setPlaceholderText(translate("Franky", "Body name"))

        self.color_button = QtWidgets.QPushButton(parent=parent)
        self.color_button.setAccessibleName(translate("Franky", "Body color"))
        self.color_button.setToolTip(translate("Franky", "Select body color"))
        self.color_button.setFixedWidth(COLOR_SWATCH_WIDTH)
        self.color_button.clicked.connect(self._select_color)
        self.color = body_color_to_qcolor(color=self.default_color)
        self._update_color_button()

        self.sketch_plane_combo = self._combo(parent=parent, values=PLANE_CHOICES)
        self.datum_plane_combo = self._combo(parent=parent, values=PLANE_CHOICES)
        self.datum_line_combo = self._combo(parent=parent, values=AXIS_CHOICES)

        self.datum_point_checkbox = QtWidgets.QCheckBox(parent=parent)
        self.datum_point_checkbox.setToolTip(translate("Franky", "Create datum point"))

        self.description_edit = QtWidgets.QLineEdit(parent=parent)
        self.description_edit.setPlaceholderText(translate("Franky", "Description"))

    def template(self, ordered_index: int) -> BodyTemplate | None:
        name = self.name_edit.text().strip()
        if not name:
            return None

        return BodyTemplate(
            index=ordered_index,
            name=name,
            color=qcolor_to_body_color(color=self.color),
            sketch_plane=self._current_combo_value(combo=self.sketch_plane_combo),
            datum_plane=self._current_combo_value(combo=self.datum_plane_combo),
            datum_line=self._current_combo_value(combo=self.datum_line_combo),
            create_datum_point=self.datum_point_checkbox.isChecked(),
            description=self.description_edit.text().strip(),
        )

    def reset(self) -> None:
        self.name_edit.clear()
        self.color = body_color_to_qcolor(color=self.default_color)
        self._update_color_button()
        self.sketch_plane_combo.setCurrentIndex(0)
        self.datum_plane_combo.setCurrentIndex(0)
        self.datum_line_combo.setCurrentIndex(0)
        self.datum_point_checkbox.setChecked(False)
        self.description_edit.clear()

    def _select_color(self) -> None:
        color = QtWidgets.QColorDialog.getColor(
            self.color,
            self.name_edit,
            translate("Franky", "Select body color"),
        )
        if color.isValid():
            self.color = color
            self._update_color_button()

    def _update_color_button(self) -> None:
        color_name = self.color.name()
        self.color_button.setStyleSheet(
            f"QPushButton {{ background-color: {color_name}; border: 1px solid #777; }}"
        )

    def _combo(self, parent: Any, values: tuple[str, ...]) -> Any:
        combo = QtWidgets.QComboBox(parent=parent)
        for value in values:
            combo.addItem(translate("Franky", value), value)
        combo.setCurrentIndex(0)
        return combo

    def _current_combo_value(self, combo: Any) -> str:
        data = combo.itemData(combo.currentIndex())
        return "" if data is None else str(data)


class NewProjectDialog(QtWidgets.QDialog):
    """Dialog for creating a new Franky project."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.rows: list[BodyTemplateRow] = []

        self.setWindowTitle(translate("Franky", "New Project"))
        self.setWindowIcon(QtGui.QIcon(Resources.icon(path="newproject.svg")))
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

        self.project_name_edit = QtWidgets.QLineEdit(parent=self)
        self.project_name_edit.setPlaceholderText(PROJECT_NAME_PLACEHOLDER)

        project_layout = QtWidgets.QHBoxLayout()
        project_layout.setContentsMargins(0, 0, 0, 0)
        project_layout.setSpacing(LAYOUT_SPACING)
        project_layout.addWidget(QtWidgets.QLabel(translate("Franky", "Project name"), parent=self))
        project_layout.addWidget(self.project_name_edit, 1)

        rows_layout = QtWidgets.QGridLayout()
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setHorizontalSpacing(LAYOUT_SPACING)
        rows_layout.setVerticalSpacing(LAYOUT_SPACING)
        self._add_headers(layout=rows_layout)

        for row_index in range(BODY_ROW_COUNT):
            row = BodyTemplateRow(parent=self, index=row_index + 1)
            self.rows.append(row)
            self._add_row(layout=rows_layout, row=row, grid_row=row_index + 1)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(LAYOUT_SPACING)

        self.create_button = QtWidgets.QPushButton(translate("Franky", "Create Project"), parent=self)
        self.create_button.clicked.connect(self._create_project)
        self.reset_button = QtWidgets.QPushButton(translate("Franky", "Reset"), parent=self)
        self.reset_button.clicked.connect(self.reset)
        self.cancel_button = QtWidgets.QPushButton(translate("Franky", "Cancel"), parent=self)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addStretch(1)
        button_layout.addWidget(self.create_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addWidget(self.cancel_button)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(DIALOG_PADDING, DIALOG_PADDING, DIALOG_PADDING, DIALOG_PADDING)
        layout.setSpacing(LAYOUT_SPACING)
        layout.addLayout(project_layout)
        layout.addLayout(rows_layout)
        layout.addLayout(button_layout)
        self.setLayout(layout)
        self.project_name_edit.setFocus()

    def reset(self) -> None:
        """Reset all project inputs."""
        self.project_name_edit.clear()
        for row in self.rows:
            row.reset()

        self.project_name_edit.setFocus()

    def project_name(self) -> str:
        """Return the trimmed project name."""
        return str(self.project_name_edit.text()).strip()

    def body_templates(self) -> list[BodyTemplate]:
        """Return body templates for all named body rows."""
        templates: list[BodyTemplate] = []
        for row in self.rows:
            template = row.template(ordered_index=len(templates) + 1)
            if template is not None:
                templates.append(template)

        return templates

    def _create_project(self) -> None:
        project_name = self.project_name()
        if not is_safe_filename(project_name):
            App.Console.PrintError("Please enter a project name that can be used as a Windows filename.\n")
            return

        try:
            create_project(project_name=project_name, body_templates=self.body_templates())
        except Exception as error:
            App.Console.PrintError(f"Could not create project: {error}\n")
            return

        self.accept()

    def _add_headers(self, layout: Any) -> None:
        headers = [
            "",
            translate("Franky", "Body"),
            translate("Franky", "Color"),
            translate("Franky", "Sketch Plane"),
            translate("Franky", "Datum Plane"),
            translate("Franky", "Datum Line"),
            translate("Franky", "Datum Point"),
            translate("Franky", "Description"),
        ]
        for column, header in enumerate(headers):
            label = QtWidgets.QLabel(header, parent=self)
            label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            layout.addWidget(label, 0, column)

    def _add_row(self, layout: Any, row: BodyTemplateRow, grid_row: int) -> None:
        number_label = QtWidgets.QLabel(f"{row.index:02d}_", parent=self)
        number_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        layout.addWidget(number_label, grid_row, 0)
        layout.addWidget(row.name_edit, grid_row, 1)
        layout.addWidget(row.color_button, grid_row, 2)
        layout.addWidget(row.sketch_plane_combo, grid_row, 3)
        layout.addWidget(row.datum_plane_combo, grid_row, 4)
        layout.addWidget(row.datum_line_combo, grid_row, 5)
        layout.addWidget(row.datum_point_checkbox, grid_row, 6, QtCore.Qt.AlignCenter)
        layout.addWidget(row.description_edit, grid_row, 7)


class NewProjectCommand:
    """Create a new FreeCAD project with a Franky starter structure."""

    Name: ClassVar[str] = "Franky_NewProject"

    def GetResources(self) -> dict[str, str]:
        return {
            "Pixmap": Resources.icon(path="newproject.svg"),
            "MenuText": translate(
                "Franky",
                "New Project",
            ),
            "ToolTip": translate(
                "Franky",
                "Create a new project with a predefined structure",
            ),
        }

    def Activated(self) -> None:
        parent = Gui.getMainWindow() if hasattr(Gui, "getMainWindow") else None
        dialog = NewProjectDialog(parent=parent)
        dialog.exec_()

    def IsActive(self) -> bool:
        return bool(App.GuiUp)

    @classmethod
    def Install(cls) -> None:
        if App.GuiUp:
            App.Gui.addCommand(cls.Name, cls())
