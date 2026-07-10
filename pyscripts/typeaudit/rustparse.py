"""Serde-aware parser for Rust structs and tagged enums.

Targeted at Rankless's declaration style (one field or `#[serde(...)]` per line,
derives on their own line) rather than a general Rust grammar. Produces the JSON
keys each Serialize/Deserialize type actually emits, applying `rename`,
`rename_all`, `flatten`, and dropping `skip`/`skip_serializing` fields.
"""

import re
from dataclasses import dataclass, field

from pyscripts.typeaudit import FieldInfo, Shape

_DERIVE_RE = re.compile(r"#\[derive\(([^)]*)\)\]")
_SERDE_RE = re.compile(r"#\[serde\((.*)\)\]")
_ITEM_RE = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(struct|enum)\s+(\w+)(<[^>]*>)?\s*([({])?"
)
_FIELD_RE = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(\w+)\s*:\s*(.+?),?\s*$")
_RENAME_RE = re.compile(r'rename\s*=\s*"([^"]*)"')
_RENAME_ALL_RE = re.compile(r'rename_all\s*=\s*"([^"]*)"')


@dataclass
class RawField:
    ident: str
    type_str: str
    rename: str | None = None
    flatten: bool = False
    skip: bool = False  # never serialized (skip / skip_serializing)
    optional: bool = False  # skip_serializing_if / default -> may be absent


@dataclass
class RawStruct:
    name: str
    is_enum: bool = False
    serialize: bool = False
    deserialize: bool = False
    rename_all: str | None = None
    tag: str | None = None  # internally-tagged enum discriminant key
    fields: list[RawField] = field(default_factory=list)
    # enum only: variant name -> its own field list (empty for unit variants)
    variants: dict[str, list[RawField]] = field(default_factory=dict)
    source: str = ""


def parse_rust(text: str, file_label: str = "") -> dict[str, RawStruct]:
    """All named structs/enums in `text`, keyed by type name."""
    out: dict[str, RawStruct] = {}
    lines = text.splitlines()
    attrs: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("#["):
            attrs.append(stripped)
            i += 1
            continue
        item = _ITEM_RE.match(line)
        if item and item.group(4) == "{":
            struct, end = _consume_item(lines, i, item, attrs, file_label)
            out[struct.name] = struct
            i = end
            attrs = []
            continue
        if stripped and not stripped.startswith("//"):
            attrs = []  # attrs only bind to the immediately-following item
        i += 1
    return out


def serialized_keys(
    name: str, registry: dict[str, RawStruct]
) -> dict[str, FieldInfo] | None:
    """JSON keys a struct emits, expanding `flatten` fields recursively."""
    struct = registry.get(name)
    if struct is None or struct.is_enum:
        return None
    keys: dict[str, FieldInfo] = {}
    for f in struct.fields:
        if f.skip:
            continue
        if f.flatten:
            inner = serialized_keys(_type_name(f.type_str), registry)
            if inner is not None:
                keys.update(inner)
            continue
        keys[_json_key(f, struct.rename_all)] = FieldInfo(f.optional, f.type_str)
    return keys


def shape_of(name: str, registry: dict[str, RawStruct]) -> Shape | None:
    keys = serialized_keys(name, registry)
    if keys is None:
        return None
    return Shape(name, keys, registry[name].source)


def _consume_item(
    lines: list[str], start: int, item: re.Match, attrs: list[str], file_label: str
) -> tuple[RawStruct, int]:
    is_enum = item.group(1) == "enum"
    struct = RawStruct(
        name=item.group(2),
        is_enum=is_enum,
        source=f"{file_label}:{start + 1}",
    )
    for attr in attrs:
        if m := _DERIVE_RE.search(attr):
            traits = {t.strip() for t in m.group(1).split(",")}
            struct.serialize = "Serialize" in traits
            struct.deserialize = "Deserialize" in traits
        if s := _SERDE_RE.search(attr):
            body = s.group(1)
            if r := _RENAME_ALL_RE.search(body):
                struct.rename_all = r.group(1)
            if tm := re.search(r'tag\s*=\s*"([^"]*)"', body):
                struct.tag = tm.group(1)
    end = (
        _parse_enum(lines, start, struct)
        if is_enum
        else _parse_struct(lines, start, struct)
    )
    return struct, end


def _parse_struct(lines: list[str], start: int, struct: RawStruct) -> int:
    i, pending = start + 1, []
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("}"):
            return i + 1
        if stripped.startswith("#["):
            pending.append(stripped)
        elif stripped and not stripped.startswith("//"):
            if fld := _field(lines[i], pending):
                struct.fields.append(fld)
            pending = []
        i += 1
    return i


def _parse_enum(lines: list[str], start: int, struct: RawStruct) -> int:
    """Variant names + their inline field sets (for internally-tagged enums).

    Depth is measured *before* the current line's braces so a struct-variant
    header (`MergeAuthors {`) is still seen at variant level.
    """
    i, depth = start, 0
    current: str | None = None
    pending: list[str] = []
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        depth_before = depth
        depth += line.count("{") - line.count("}")
        if i == start:  # the `enum X {` header
            i += 1
            continue
        if depth_before == 1 and current is None:  # variant-declaration level
            if stripped.startswith("}"):
                return i + 1  # closes the enum
            if stripped.startswith("#["):
                pending = []
            elif m := re.match(r"^(\w+)", stripped):
                struct.variants[m.group(1)] = []
                current = m.group(1) if "{" in line else None
        elif current is not None:  # inside a struct-variant body
            if depth_before >= 2 and stripped.startswith("}"):
                current = None
            elif stripped.startswith("#["):
                pending.append(stripped)
            elif stripped and not stripped.startswith("//"):
                if fld := _field(line, pending):
                    struct.variants[current].append(fld)
                pending = []
        i += 1
    return i


def _field(line: str, attrs: list[str]) -> RawField | None:
    m = _FIELD_RE.match(line)
    if not m:
        return None
    fld = RawField(ident=m.group(1), type_str=m.group(2).strip())
    for attr in attrs:
        if s := _SERDE_RE.search(attr):
            body = s.group(1)
            if r := _RENAME_RE.search(body):
                fld.rename = r.group(1)
            fld.flatten = fld.flatten or bool(re.search(r"\bflatten\b", body))
            if re.search(r"\bskip\b|\bskip_serializing\b(?!_if)", body):
                fld.skip = True
            if "skip_serializing_if" in body or re.search(r"\bdefault\b", body):
                fld.optional = True
    if fld.type_str.startswith("Option<"):
        fld.optional = True
    return fld


def _json_key(f: RawField, rename_all: str | None) -> str:
    if f.rename is not None:
        return f.rename
    return _apply_case(f.ident, rename_all) if rename_all else f.ident


def _type_name(type_str: str) -> str:
    return re.sub(r"<.*", "", type_str).strip().rsplit("::", 1)[-1]


def _apply_case(ident: str, style: str) -> str:
    parts = ident.split("_")
    if style == "snake_case":
        return ident
    if style == "kebab-case":
        return "-".join(parts)
    if style == "SCREAMING_SNAKE_CASE":
        return ident.upper()
    if style == "camelCase":
        return parts[0] + "".join(p.title() for p in parts[1:])
    if style == "PascalCase":
        return "".join(p.title() for p in parts)
    return ident


def variant_tag(variant: str, rename_all: str | None) -> str:
    """Enum variant name -> its serde tag value (PascalCase source ident)."""
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", variant).lower()
    parts = snake.split("_")
    if rename_all == "snake_case" or rename_all is None:
        return snake
    if rename_all == "kebab-case":
        return "-".join(parts)
    if rename_all == "camelCase":
        return parts[0] + "".join(p.title() for p in parts[1:])
    return variant
