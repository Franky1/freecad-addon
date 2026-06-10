# Agent Instructions

- This is a personal FreeCAD addon workbench named `Franky`; keep changes small and FreeCAD-focused.
- Main source lives in `freecad/franky/`; command classes live one-per-file in `freecad/franky/commands/`.
- FreeCAD GUI code must guard registration with `App.GuiUp`; avoid importing GUI-only modules in non-GUI paths unless existing code already does.
- Preserve command names such as `Franky_ExportStep`; changing them can break saved toolbars, macros, and user workflows.
- New commands should implement `GetResources()`, `Activated()`, `IsActive()`, and `Install()`, then be exported from `commands/__init__.py` and added to `workbench.py` as needed.
- Use `Resources.icon(...)` for icons and `App.Qt.translate("Franky", "...")` for visible command text.
- Export commands expect an active, saved document and selected objects; keep user errors in `App.Console.PrintError(...)`.
- This project targets Windows first, FreeCAD 1.1.1+, and Python 3.10+; keep cross-platform behavior only where it is already supported.
- Style: Python 3.11 typing, Ruff line length 120, double quotes, strict mypy intent. Keep SPDX headers.
- Prefer `pathlib.Path`, explicit return types, and narrow changes over broad refactors.
- Do not auto-delete unused imports or move FreeCAD imports just to satisfy style; `pyproject.toml` marks `F401` and `E402` unfixable.
- Validate with `ruff check .` and `mypy freecad` when practical; many FreeCAD behaviors still require manual testing inside FreeCAD.
- Keep `package.xml`, `README.md`, and `freecad/franky/resources/docs/Overview.md` in sync for user-facing addon metadata.
