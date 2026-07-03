"""Minimal parser for the TypeScript type declarations Rankless uses.

Handles `export type X = { ... }`, `export interface X { ... }`, and
`kind`-discriminated unions (`export type P = | { kind: 'a'; ... } | ...`).
Compares top-level keys only — it does not resolve referenced types (the Rust
side expands `flatten`; TS has no equivalent), and it drops the `kind`
discriminant from union variants so they line up with Rust's separate tag.
"""

import re
from dataclasses import dataclass, field

from pyscripts.typeaudit import FieldInfo

# Anchored at line start so `import type Foo` (line starts with `import`) is
# never matched; `export` is optional so local (unexported) aliases are caught.
_DECL_RE = re.compile(
    r"^[^\S\n]*(?:export\s+)?(type|interface)\s+(\w+)[^\S\n]*(=)?", re.MULTILINE
)
_MEMBER_RE = re.compile(r"^(\w+)\s*(\?)?\s*:")
_KIND_RE = re.compile(r"kind\s*:\s*'([^']*)'")
_OPEN = {"{": "}", "[": "]", "(": ")", "<": ">"}


@dataclass
class TsType:
    name: str
    keys: dict[str, FieldInfo] = field(default_factory=dict)
    # `kind`-discriminated union variants: tag -> its (non-kind) keys
    variants: dict[str, dict[str, FieldInfo]] | None = None
    source: str = ""


def parse_ts(text: str, file_label: str = "") -> dict[str, TsType]:
    out: dict[str, TsType] = {}
    for m in _DECL_RE.finditer(text):
        kind, name = m.group(1), m.group(2)
        line = f"{file_label}:{text.count(chr(10), 0, m.start()) + 1}"
        if kind == "interface":
            body, _ = _brace_block(text, text.index("{", m.end()))
            out[name] = TsType(name, keys=_object_fields(body), source=line)
        else:
            rhs, _ = _read_rhs(text, m.end())
            out[name] = _classify(name, rhs, line)
    return out


def _classify(name: str, rhs: str, line: str) -> TsType:
    blocks = _top_level_blocks(rhs)
    variants: dict[str, dict[str, FieldInfo]] = {}
    for block in blocks:
        if tag := _KIND_RE.search(block):
            keys = _object_fields(block)
            keys.pop("kind", None)
            variants[tag.group(1)] = keys
    if variants:
        return TsType(name, variants=variants, source=line)
    if len(blocks) == 1:
        return TsType(name, keys=_object_fields(blocks[0]), source=line)
    return TsType(name, source=line)  # literal union / alias: no object shape


def _object_fields(body: str) -> dict[str, FieldInfo]:
    keys: dict[str, FieldInfo] = {}
    for member in _split_top_level(_strip_comments(body)):
        member = member.strip()
        if not member:
            continue
        if fm := _MEMBER_RE.match(member):
            keys[fm.group(1)] = FieldInfo(
                optional=bool(fm.group(2)), type_str=member[fm.end() :].strip()
            )
    return keys


def _brace_block(text: str, open_idx: int) -> tuple[str, int]:
    """Inner text of the `{...}` starting at open_idx, and the index past `}`."""
    depth, i = 0, open_idx
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1 : i], i + 1
        i += 1
    return text[open_idx + 1 :], len(text)


def _read_rhs(text: str, pos: int) -> tuple[str, int]:
    """Type-alias RHS from pos up to the terminating top-level `;`."""
    stack, i = [], pos
    while i < len(text):
        ch = text[i]
        if ch in _OPEN:
            stack.append(_OPEN[ch])
        elif stack and ch == stack[-1]:
            stack.pop()
        elif ch == ";" and not stack:
            return text[pos:i], i + 1
        i += 1
    return text[pos:], len(text)


def _top_level_blocks(rhs: str) -> list[str]:
    """Inner text of every top-level `{...}` in a type-alias RHS."""
    blocks, i = [], 0
    while i < len(rhs):
        if rhs[i] == "{":
            inner, end = _brace_block(rhs, i)
            blocks.append(inner)
            i = end
        else:
            i += 1
    return blocks


def _split_top_level(body: str) -> list[str]:
    """Split object members on `;`/newline at bracket depth 0."""
    out, stack, start = [], [], 0
    for i, ch in enumerate(body):
        if ch in _OPEN:
            stack.append(_OPEN[ch])
        elif stack and ch == stack[-1]:
            stack.pop()
        elif ch in ";\n" and not stack:
            out.append(body[start:i])
            start = i + 1
    out.append(body[start:])
    return out


def _strip_comments(body: str) -> str:
    return re.sub(r"//[^\n]*", "", body)
