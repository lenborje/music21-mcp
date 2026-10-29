"""Passive metadata discovery. Discovery never grants read or call permission."""

import ast
import inspect
import math
import sys
import types
import typing
from dataclasses import dataclass
from functools import lru_cache
from textwrap import dedent
from typing import Any

from .adapters.music21 import readable_names
from .pagination import json_size, page, validate_bytes
from .registry import APIError

MAX_DOC = 1200
MAX_TYPE = 256
MAX_PARAMETERS = 32
MISSING = object()


def qualified(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


def annotation_text(value: Any) -> str | None:
    if value is inspect.Signature.empty or value is MISSING:
        return None
    if isinstance(value, str):
        return value[:MAX_TYPE]
    if value is None:
        return "None"
    if isinstance(value, type):
        return (value.__name__ if value.__module__ == "builtins" else qualified(value))[:MAX_TYPE]
    if value is Ellipsis:
        return "..."
    if (
        isinstance(value, (types.GenericAlias, types.UnionType))
        or type(value).__module__ == "typing"
    ):
        origin = typing.get_origin(value)
        args = typing.get_args(value)
        if origin in (typing.Union, types.UnionType):
            return " | ".join(annotation_text(arg) or "?" for arg in args)[:MAX_TYPE]
        if isinstance(origin, type):
            name = annotation_text(origin)
            return f"{name}[{', '.join(annotation_text(arg) or '?' for arg in args)}]"[:MAX_TYPE]
        if isinstance(value, typing.ForwardRef):
            return value.__forward_arg__[:MAX_TYPE]
        if isinstance(value, typing.TypeVar):
            return value.__name__[:MAX_TYPE]
    # Do not call arbitrary repr or evaluate forward references.
    return None


@lru_cache(maxsize=512)
def source_annotations(value: Any) -> dict[str, Any]:
    """Parse declaration text; even annotationlib's STRING format can execute code."""
    try:
        nodes = ast.parse(dedent(inspect.getsource(value))).body
    except (OSError, TypeError, SyntaxError, IndentationError):
        return {}
    name = value.__name__
    node = next(
        (
            n
            for n in nodes
            if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name == name
        ),
        None,
    )
    hints: dict[str, Any] = {}

    def text(annotation: ast.expr) -> str:
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            return annotation.value
        return ast.unparse(annotation)

    if isinstance(node, ast.ClassDef):
        for declaration in node.body:
            if isinstance(declaration, ast.AnnAssign) and isinstance(declaration.target, ast.Name):
                hints[declaration.target.id] = text(declaration.annotation)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        args = node.args
        for parameter in [
            *args.posonlyargs,
            *args.args,
            *args.kwonlyargs,
            *([args.vararg] if args.vararg else []),
            *([args.kwarg] if args.kwarg else []),
        ]:
            if parameter.annotation is not None:
                hints[parameter.arg] = text(parameter.annotation)
        if node.returns is not None:
            hints["return"] = text(node.returns)
    return hints


def annotations(value: Any) -> dict[str, Any]:
    if sys.version_info >= (3, 14):
        # Do not access __annotations__ or call __annotate__ on deferred functions.
        # A class may still have an explicit, already stored annotation dictionary.
        if isinstance(value, type):
            stored = vars(value).get("__annotations__")
            if isinstance(stored, dict):
                return dict(stored)
        return source_annotations(value)
    try:
        return inspect.get_annotations(value, eval_str=False)
    except (TypeError, ValueError):
        return {}


def signature(function: Any) -> inspect.Signature | None:
    if not inspect.isfunction(function):
        return None
    # A new function with the same argument layout/defaults but no annotations
    # lets inspect extract parameter kinds without executing deferred expressions.
    clone = types.FunctionType(
        function.__code__,
        function.__globals__,
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    clone.__kwdefaults__ = function.__kwdefaults__
    try:
        sig = inspect.signature(clone, eval_str=False, follow_wrapped=False)
    except (TypeError, ValueError):
        return None
    hints = annotations(function)
    return sig.replace(
        parameters=[
            p.replace(annotation=hints.get(p.name, p.empty)) for p in sig.parameters.values()
        ],
        return_annotation=hints.get("return", sig.empty),
    )


def documentation(value: Any) -> dict[str, Any]:
    text = inspect.cleandoc(value) if isinstance(value, str) else ""
    return {"text": text[:MAX_DOC], "truncated": len(text) > MAX_DOC}


def literal(value: Any) -> dict[str, Any]:
    if value is None or type(value) in (str, bool, int):
        if isinstance(value, str) and len(value) > 128:
            return {"type": "str", "truncated": True}
        return {"value": value}
    if type(value) is float and math.isfinite(value):
        return {"value": value}
    return {"type": qualified(type(value))}


@dataclass
class Member:
    name: str
    kind: str
    owner: type
    value: Any = MISSING
    doc: str = ""
    hint: Any = MISSING
    source: str = "class"
    stored_type: str | None = None


def discover(cls: type, obj: object | None = None) -> dict[str, Member]:
    """Read namespaces rather than dir/getmembers, which can invoke descriptors."""
    members: dict[str, Member] = {}
    for owner in reversed(cls.__mro__):
        if owner is object:
            continue
        namespace = vars(owner)
        hints = annotations(owner)
        docs = namespace.get("_DOC_ATTR", {})
        if not isinstance(docs, dict):
            docs = {}
        names = set(namespace) | set(hints) | set(docs)
        for name in sorted(n for n in names if isinstance(n, str) and not n.startswith("_")):
            value = namespace.get(name, MISSING)
            hint = hints.get(name, MISSING)
            doc = docs.get(name, "")
            source = "class"
            if isinstance(value, property):
                kind = "property"
                doc = value.__doc__ or doc
                sig = signature(value.fget) if value.fget else None
                hint = sig.return_annotation if sig else hint
                source = "property"
            elif isinstance(value, (staticmethod, classmethod)) or inspect.isfunction(value):
                kind = "method"
                function = (
                    value.__func__ if isinstance(value, (staticmethod, classmethod)) else value
                )
                doc = function.__doc__ or doc
            elif inspect.ismemberdescriptor(value) or inspect.isgetsetdescriptor(value):
                kind = "attribute"
                source = "slot"
            elif value is MISSING:
                kind = "attribute"
                source = "annotation" if name in hints else "music21_docs"
            elif value is None or type(value) in (str, bool, int, float, tuple, list, dict):
                kind = "attribute"
            else:
                continue  # Exclude modules, classes, unknown descriptors and Python internals.
            # Inherited _DOC_ATTR dictionaries may repeat names. Keep the actual descriptor.
            if value is MISSING and name in members:
                if doc and not members[name].doc:
                    members[name].doc = doc
                continue
            members[name] = Member(name, kind, owner, value, doc, hint, source)
    if obj is not None:
        # Only use the built-in instance-dictionary descriptor from the MRO,
        # never a user-defined descriptor or a metaclass's __dict__.
        stored: Any = {}
        for owner in cls.__mro__:
            descriptor = vars(owner).get("__dict__")
            if inspect.isgetsetdescriptor(descriptor) and descriptor.__objclass__ is owner:
                stored = descriptor.__get__(obj, cls)
                break
        if isinstance(stored, dict):
            for name in stored:
                if not isinstance(name, str) or name.startswith("_"):
                    continue
                if name not in members:
                    members[name] = Member(name, "attribute", cls, source="instance")
                if members[name].kind == "attribute":
                    members[name].stored_type = qualified(type(stored[name]))
    for name in readable_names(cls):
        if name not in members:
            members[name] = Member(name, "property", cls, source="adapter")
    return members


def method_info(member: Member) -> dict[str, Any]:
    raw = member.value
    function = raw.__func__ if isinstance(raw, (staticmethod, classmethod)) else raw
    sig = signature(function)
    if sig is None:
        return {
            "signature": None,
            "signature_truncated": False,
            "parameters": [],
            "return_type": None,
            "return_type_truncated": False,
            "parameters_truncated": False,
        }
    parameters = list(sig.parameters.values())
    if not isinstance(raw, staticmethod) and parameters:
        parameters = parameters[1:]
    result = []
    display = []
    for index, p in enumerate(parameters[:MAX_PARAMETERS]):
        hint = annotation_text(p.annotation)
        entry: dict[str, Any] = {
            "name": p.name,
            "kind": p.kind.name,
            "type_hint": hint,
            "type_hint_truncated": isinstance(p.annotation, str) and len(p.annotation) > MAX_TYPE,
            "required": p.default is p.empty and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD),
        }
        prefix = "*" if p.kind is p.VAR_POSITIONAL else "**" if p.kind is p.VAR_KEYWORD else ""
        text = prefix + p.name + (f": {hint}" if hint else "")
        if p.kind is p.KEYWORD_ONLY and index == 0:
            display.append("*")
        elif (
            p.kind is p.KEYWORD_ONLY
            and index
            and parameters[index - 1].kind
            not in (
                p.KEYWORD_ONLY,
                p.VAR_POSITIONAL,
            )
        ):
            display.append("*")
        if p.default is not p.empty:
            entry["default"] = literal(p.default)
            safe = entry["default"]
            text += " = " + (repr(safe["value"]) if "value" in safe else "<non-literal>")
        result.append(entry)
        display.append(text)
        if p.kind is p.POSITIONAL_ONLY and (
            index + 1 == len(parameters) or parameters[index + 1].kind is not p.POSITIONAL_ONLY
        ):
            display.append("/")
    return_type = annotation_text(sig.return_annotation)
    if len(parameters) > MAX_PARAMETERS:
        display.append("...")
    text = "(" + ", ".join(display) + ")" + (f" -> {return_type}" if return_type else "")
    return {
        "signature": text[:2048],
        "signature_truncated": len(text) > 2048,
        "parameters": result,
        "parameters_truncated": len(parameters) > MAX_PARAMETERS,
        "return_type": return_type,
        "return_type_truncated": isinstance(sig.return_annotation, str)
        and len(sig.return_annotation) > MAX_TYPE,
    }


def describe(member: Member, cls: type) -> dict[str, Any]:
    readable = member.name in readable_names(cls)
    result: dict[str, Any] = {
        "name": member.name,
        "kind": member.kind,
        "defined_on": qualified(member.owner),
        "source": member.source,
        "readable": readable,
        "writable": False,
        "callable": False,
        "doc": documentation(member.doc),
    }
    if member.kind == "method":
        result.update(method_info(member))
        result["restriction"] = "Method calls are not exposed in the read-only API"
    else:
        hint = annotation_text(member.hint)
        result["type_hint"] = hint
        result["type_hint_truncated"] = isinstance(member.hint, str) and len(member.hint) > MAX_TYPE
        result["stored_type"] = member.stored_type
        result["wire_format"] = "rational" if member.name == "quarterLength" else "value_or_ref"
        if not readable:
            result["restriction"] = "Not in the reviewed read policy"
    return result


def schema(
    cls: type,
    obj: object | None = None,
    kind: str | None = None,
    offset: int = 0,
    limit: int = 50,
    max_bytes: int = 262_144,
) -> dict[str, Any]:
    page([], offset, limit)
    validate_bytes(max_bytes)
    if kind not in (None, "property", "attribute", "method"):
        raise APIError("invalid_schema: kind must be property, attribute or method")
    members = discover(cls, obj)
    selected = sorted(
        (m for m in members.values() if kind is None or m.kind == kind), key=lambda m: m.name
    )
    result: dict[str, Any] = {
        "type": qualified(cls),
        "doc": documentation(vars(cls).get("__doc__", "")),
        "bases": [qualified(c) for c in cls.__mro__[1:] if c is not object][:16],
        "read_only": True,
        "items": [],
        "total": len(selected),
        "next_offset": None,
    }
    # next_offset can grow up to 100000; reserve space for its digits.
    size = json_size(result) + 16
    for member in selected[offset : offset + limit]:
        item = describe(member, cls)
        candidate = json_size(item) + 1
        if size + candidate > max_bytes:
            if not result["items"]:
                raise APIError("result_too_large: Schema member exceeds max_bytes")
            break
        result["items"].append(item)
        size += candidate
    end = offset + len(result["items"])
    result["next_offset"] = end if end < len(selected) else None
    if json_size(result) > max_bytes:
        raise APIError("result_too_large: Schema header exceeds max_bytes")
    return result
