use std::collections::{BTreeMap, BTreeSet};

use serde_json::Value;

use crate::{
    config::PythonStyle,
    error::Error,
    model::{ConstDef, Model, Modules},
    output::header,
    shape::{Field, Shape},
};

const KEYWORDS: [&str; 35] = [
    "False", "None", "True", "and", "as", "assert", "async", "await", "break", "class", "continue",
    "def", "del", "elif", "else", "except", "finally", "for", "from", "global", "if", "import",
    "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try", "while",
    "with", "yield",
];

/// One module file being rendered: its declarations so far and what they import.
struct File<'a> {
    model: &'a Model,
    module: &'a str,
    style: PythonStyle,
    modules: &'a Modules<'a>,
    body: Vec<String>,
    names: BTreeSet<String>,
    imports: BTreeMap<String, BTreeSet<String>>,
    typing: BTreeSet<&'static str>,
}

impl<'a> File<'a> {
    fn new(
        model: &'a Model,
        module: &'a str,
        style: PythonStyle,
        modules: &'a Modules<'a>,
    ) -> Self {
        Self {
            model,
            module,
            style,
            modules,
            body: Vec::new(),
            names: BTreeSet::new(),
            imports: BTreeMap::new(),
            typing: BTreeSet::new(),
        }
    }

    /// The module's values as one block of `Final` assignments.
    fn constants(&mut self, consts: &[&ConstDef]) -> Result<(), Error> {
        if consts.is_empty() {
            return Ok(());
        }
        self.typing.insert("Final");
        let mut block = String::new();
        for c in consts {
            self.claim(&c.name)?;
            let doc = c.doc.as_deref().map(|d| comment(d, "")).unwrap_or_default();
            block += &format!("{doc}{}: Final = {}\n", c.name, python_literal(&c.value));
        }
        self.body.push(block.trim_end().to_string());
        Ok(())
    }

    fn declare(&mut self, id: usize) -> Result<(), Error> {
        let t = &self.model.types[id];
        match &t.shape {
            Shape::Object(_) | Shape::Intersection(_) => {
                let fields = self.fields_of(&t.shape, &t.name)?;
                self.class(&t.name, &fields, t.doc.as_deref())
            }
            other => {
                self.claim(&t.name)?;
                let value = self.expr(other, &t.name)?;
                let doc = t.doc.as_deref().map(|d| comment(d, "")).unwrap_or_default();
                self.body.push(format!("{doc}type {} = {value}", t.name));
                Ok(())
            }
        }
    }

    fn class(&mut self, name: &str, fields: &[Field], doc: Option<&str>) -> Result<(), Error> {
        self.claim(name)?;
        let identifiers = fields.iter().all(|f| is_identifier(&f.key));
        let mut lines = Vec::new();
        for f in fields {
            let ty = self.expr(&f.shape, &format!("{name}{}", pascal(&f.key)))?;
            lines.push((f, ty));
        }
        let doc_line = doc.map(|d| {
            let d = d.replace('"', "\\\"").replace('\n', "\n    ");
            format!("    \"\"\"{d}\"\"\"\n")
        });
        let body = match (self.style, identifiers) {
            (PythonStyle::TypedDict, true) => {
                self.typing.insert("TypedDict");
                let mut s = format!("class {name}(TypedDict):\n{}", doc_line.unwrap_or_default());
                for (f, ty) in &lines {
                    s += &f
                        .doc
                        .as_deref()
                        .map(|d| comment(d, "    "))
                        .unwrap_or_default();
                    s += &format!("    {}: {}\n", f.key, self.optional(f, ty));
                }
                with_pass(s, fields.is_empty())
            }
            (PythonStyle::TypedDict, false) => {
                self.typing.insert("TypedDict");
                let doc = doc.map(|d| comment(d, "")).unwrap_or_default();
                let mut s = format!("{doc}{name} = TypedDict(\n    \"{name}\",\n    {{\n");
                for (f, ty) in &lines {
                    s += &f
                        .doc
                        .as_deref()
                        .map(|d| comment(d, "        "))
                        .unwrap_or_default();
                    let ty = self.optional(f, ty).replace('\'', "\\'");
                    s += &format!("        {}: '{ty}',\n", Value::String(f.key.clone()));
                }
                s + "    },\n)"
            }
            (PythonStyle::Dataclass, false) => {
                let key = fields.iter().find(|f| !is_identifier(&f.key)).unwrap();
                return Err(Error::PythonField {
                    owner: format!("{}::{name}", self.module),
                    key: key.key.clone(),
                });
            }
            (PythonStyle::Dataclass, true) => {
                let mut s = format!(
                    "@dataclass(kw_only=True)\nclass {name}:\n{}",
                    doc_line.unwrap_or_default()
                );
                for (f, ty) in &lines {
                    s += &f
                        .doc
                        .as_deref()
                        .map(|d| comment(d, "    "))
                        .unwrap_or_default();
                    s += &match (f.required, ty.ends_with("| None")) {
                        (true, _) => format!("    {}: {ty}\n", f.key),
                        (false, true) => format!("    {}: {ty} = None\n", f.key),
                        (false, false) => format!("    {}: {ty} | None = None\n", f.key),
                    };
                }
                with_pass(s, fields.is_empty())
            }
        };
        self.body.push(body.trim_end().to_string());
        Ok(())
    }

    fn optional(&mut self, f: &Field, ty: &str) -> String {
        match f.required {
            true => ty.to_string(),
            false => {
                self.typing.insert("NotRequired");
                format!("NotRequired[{ty}]")
            }
        }
    }

    /// The Python type expression for `shape`; an inline object becomes a class named `hint`.
    fn expr(&mut self, shape: &Shape, hint: &str) -> Result<String, Error> {
        Ok(match shape {
            Shape::Any => {
                self.typing.insert("Any");
                "Any".into()
            }
            Shape::Null => "None".into(),
            Shape::Bool => "bool".into(),
            Shape::Int => "int".into(),
            Shape::Float => "float".into(),
            Shape::Str => "str".into(),
            Shape::Literal(v) => self.literal(&[v]),
            Shape::Array(inner) => format!("list[{}]", self.expr(inner, hint)?),
            Shape::Tuple(items) => {
                let items = items
                    .iter()
                    .enumerate()
                    .map(|(i, item)| self.expr(item, &format!("{hint}{}", i + 1)))
                    .collect::<Result<Vec<_>, _>>()?;
                format!("tuple[{}]", items.join(", "))
            }
            Shape::Map(values) => format!("dict[str, {}]", self.expr(values, hint)?),
            Shape::Object(_) | Shape::Intersection(_) => {
                let fields = self.fields_of(shape, hint)?;
                self.class(hint, &fields, None)?;
                hint.to_string()
            }
            Shape::Union(members) => self.union(members, hint)?,
            Shape::Ref(id) => {
                let t = &self.model.types[*id];
                if t.module != self.module {
                    self.imports
                        .entry(t.module.clone())
                        .or_default()
                        .insert(t.name.clone());
                }
                t.name.clone()
            }
        })
    }

    fn union(&mut self, members: &[Shape], hint: &str) -> Result<String, Error> {
        let tag = Shape::discriminator(members);
        let mut parts = Vec::new();
        let mut literals: Vec<&Value> = Vec::new();
        for (i, m) in members.iter().enumerate() {
            if let Shape::Literal(v) = m {
                literals.push(v);
                continue;
            }
            if !literals.is_empty() {
                parts.push(self.literal(&literals));
                literals.clear();
            }
            // the variant's tag value, or the sole key of an externally tagged variant
            let suffix = match (&tag, m) {
                (Some(tag), Shape::Object(fields)) => fields
                    .iter()
                    .find(|f| &f.key == tag)
                    .and_then(|f| match &f.shape {
                        Shape::Literal(Value::String(s)) => Some(pascal(s)),
                        _ => None,
                    }),
                (None, Shape::Object(fields)) if fields.len() == 1 => Some(pascal(&fields[0].key)),
                _ => None,
            }
            .unwrap_or_else(|| (i + 1).to_string());
            let m = tag.as_deref().map_or(m.clone(), |tag| m.tag_first(tag));
            parts.push(self.expr(&m, &format!("{hint}{suffix}"))?);
        }
        if !literals.is_empty() {
            parts.push(self.literal(&literals));
        }
        Ok(parts.join(" | "))
    }

    fn literal(&mut self, values: &[&Value]) -> String {
        self.typing.insert("Literal");
        let values: Vec<String> = values.iter().map(|v| python_value(v)).collect();
        format!("Literal[{}]", values.join(", "))
    }

    /// The fields of an object shape, an intersection's merged across its members.
    fn fields_of(&self, shape: &Shape, owner: &str) -> Result<Vec<Field>, Error> {
        let mut fields = match shape {
            Shape::Object(fields) => fields.clone(),
            Shape::Ref(id) => self.fields_of(&self.model.types[*id].shape, owner)?,
            Shape::Intersection(members) => members
                .iter()
                .map(|m| self.fields_of(m, owner))
                .collect::<Result<Vec<_>, _>>()?
                .concat(),
            other => {
                return Err(Error::Unsupported {
                    owner: format!("{}::{owner}", self.module),
                    schema: format!("{other:?} as part of a Python class"),
                })
            }
        };
        if matches!(shape, Shape::Intersection(_)) {
            fields.sort_by(|a, b| a.key.cmp(&b.key));
        }
        Ok(fields)
    }

    fn claim(&mut self, name: &str) -> Result<(), Error> {
        match self.names.insert(name.to_string()) {
            true => Ok(()),
            false => Err(self.collision(name)),
        }
    }

    fn collision(&self, name: &str) -> Error {
        Error::Collision {
            file: file_path(self.module, self.modules),
            name: name.to_string(),
        }
    }

    fn finish(self, regenerate: &str) -> Result<String, Error> {
        let mut out = format!(
            "# {}\n\nfrom __future__ import annotations\n\n",
            header(self.module, regenerate)
        );
        if self.style == PythonStyle::Dataclass {
            out += "from dataclasses import dataclass\n";
        }
        if !self.typing.is_empty() {
            let typing: Vec<&str> = self.typing.iter().copied().collect();
            out += &format!("from typing import {}\n", typing.join(", "));
        }
        let package = package_of(self.module, self.modules);
        let mut imported = BTreeSet::new();
        let mut relative = String::new();
        for (module, names) in &self.imports {
            for name in names {
                if self.names.contains(name) || !imported.insert(name) {
                    return Err(self.collision(name));
                }
            }
            let target: Vec<&str> = module.split("::").collect();
            let common = package
                .iter()
                .zip(&target)
                .take_while(|(a, b)| a == b)
                .count();
            let names: Vec<&str> = names.iter().map(String::as_str).collect();
            relative += &format!(
                "from {}{} import {}\n",
                ".".repeat(package.len() - common + 1),
                target[common..].join("."),
                names.join(", ")
            );
        }
        if !relative.is_empty() {
            out += &format!("\n{relative}");
        }
        Ok(format!(
            "{}\n\n\n{}\n",
            out.trim_end(),
            self.body.join("\n\n\n")
        ))
    }
}

/// One file per module: `a::b` at `a/b.py`, or at `a/b/__init__.py` when `a::b` has submodules;
/// every package directory gets an `__init__.py`. Imports between modules are relative, so the
/// output directory can sit at any package path.
pub fn render(
    model: &Model,
    style: PythonStyle,
    regenerate: &str,
) -> Result<BTreeMap<String, String>, Error> {
    let modules = model.modules();
    let mut files = BTreeMap::new();
    for (module, contents) in &modules {
        let mut file = File::new(model, module, style, &modules);
        file.constants(&contents.consts)?;
        for &id in &contents.types {
            file.declare(id)?;
        }
        files.insert(file_path(module, &modules), file.finish(regenerate)?);
    }
    let dirs: BTreeSet<String> = files
        .keys()
        .flat_map(|path| {
            let segments: Vec<&str> = path.split('/').collect();
            (0..segments.len()).map(move |n| segments[..n].join("/"))
        })
        .collect();
    for dir in dirs {
        let init = match dir.is_empty() {
            true => "__init__.py".to_string(),
            false => format!("{dir}/__init__.py"),
        };
        files
            .entry(init)
            .or_insert_with(|| format!("# {}\n", header("", regenerate)));
    }
    Ok(files)
}

fn file_path(module: &str, modules: &Modules) -> String {
    let base = module.replace("::", "/");
    match has_submodules(module, modules) {
        true => format!("{base}/__init__.py"),
        false => format!("{base}.py"),
    }
}

/// The package segments a module's file sits in: its own for an `__init__.py`, else its parent's.
fn package_of<'m>(module: &'m str, modules: &Modules) -> Vec<&'m str> {
    let segments: Vec<&str> = module.split("::").collect();
    match has_submodules(module, modules) {
        true => segments,
        false => segments[..segments.len() - 1].to_vec(),
    }
}

fn has_submodules(module: &str, modules: &Modules) -> bool {
    let prefix = format!("{module}::");
    modules.keys().any(|m| m.starts_with(&prefix))
}

fn is_identifier(key: &str) -> bool {
    let mut chars = key.chars();
    chars
        .next()
        .is_some_and(|c| c.is_ascii_alphabetic() || c == '_')
        && chars.all(|c| c.is_ascii_alphanumeric() || c == '_')
        && !KEYWORDS.contains(&key)
}

fn pascal(s: &str) -> String {
    s.split(|c: char| !c.is_ascii_alphanumeric())
        .filter(|w| !w.is_empty())
        .map(|w| {
            let mut chars = w.chars();
            let first = chars.next().unwrap().to_ascii_uppercase();
            std::iter::once(first).chain(chars).collect::<String>()
        })
        .collect()
}

/// A value as a Python literal; arrays and tuples become tuples, which a constant cannot mutate.
fn python_literal(v: &Value) -> String {
    match v {
        Value::Array(items) => {
            let items: Vec<String> = items.iter().map(python_literal).collect();
            match items.as_slice() {
                [one] => format!("({one},)"),
                _ => format!("({})", items.join(", ")),
            }
        }
        Value::Object(fields) => {
            let fields: Vec<String> = fields
                .iter()
                .map(|(k, v)| format!("{}: {}", Value::String(k.clone()), python_literal(v)))
                .collect();
            format!("{{{}}}", fields.join(", "))
        }
        other => python_value(other),
    }
}

fn python_value(v: &Value) -> String {
    match v {
        Value::Bool(true) => "True".into(),
        Value::Bool(false) => "False".into(),
        Value::Null => "None".into(),
        other => other.to_string(),
    }
}

fn comment(doc: &str, indent: &str) -> String {
    doc.lines()
        .map(|l| format!("{indent}# {l}").trim_end().to_string() + "\n")
        .collect()
}

fn with_pass(s: String, empty: bool) -> String {
    match empty {
        true => s + "    pass\n",
        false => s,
    }
}
