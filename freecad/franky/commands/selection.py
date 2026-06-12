# SPDX-License-Identifier: LGPL-2.1-or-later

"""Selection helpers for FreeCAD commands."""

from collections.abc import Iterable
from typing import Any


def is_body(obj: Any) -> bool:
    """Return whether the object is a PartDesign Body."""
    is_derived_from = getattr(obj, "isDerivedFrom", None)
    if not callable(is_derived_from):
        return False

    return bool(is_derived_from("PartDesign::Body"))


def contains_only_bodies(objects: Iterable[Any]) -> bool:
    """Return whether all objects are PartDesign Bodies."""
    return all(is_body(obj) for obj in objects)
