use std::collections::{BTreeMap, BTreeSet};

use serde_json::Value;

use crate::{
    error::Error,
    model::Model,
    output::header,
    shape::{Field, Shape},
};

/// One `.ts` file per module, `a::b::c` at `a/b/c.ts`; types of other modules are imported.
pub fn render(model: &Model, regenerate: &str) -> Result<BTreeMap<String, String>, Error> {
    let mut files = BTreeMap::new();
    for (module, ids) in model.modules() {
        let path = format!("{}.ts", module.replace("::", "/"));
        let mut refs = BTreeSet::new();
        for &id in &ids {
            model.types[id].shape.refs(&mut refs);
        }
        let mut names: BTreeSet<&str> = ids
            .iter()
            .map(|&id| model.types[id].name.as_str())
            .collect();
        let mut imports: BTreeMap<String, Vec<&str>> = BTreeMap::new();
        for id in refs {
            let t = &model.types[id];
            if t.module == module {
                continue;
            }
            if !names.insert(&t.name) {
                return Err(Error::Collision {
                    file: path,
                    name: t.name.clone(),
                });
            }
            imports
                .entry(relative_import(module, &t.module))
                .or_default()
                .push(&t.name);
        }

        let mut out = format!("// {}\n", header(module, regenerate));
        if !imports.is_empty() {
            out += "\n";
        }
        for (from, mut names) in imports {
            names.sort_unstable();
            out += &format!("import type {{ {} }} from '{from}';\n", names.join(", "));
        }
        for id in ids {
            let t = &model.types[id];
            out += "\n";
            out += &comment(t.doc.as_deref(), "");
            let body = top_expr(&t.shape, model);
            let sep = if body.starts_with('\n') { "" } else { " " };
            out += &format!("export type {} ={sep}{body};\n", t.name);
        }
        files.insert(path, out);
    }
    Ok(files)
}

fn top_expr(shape: &Shape, model: &Model) -> String {
    match shape {
        Shape::Object(fields) if !fields.is_empty() => {
            let mut s = String::from("{\n");
            for f in fields {
                s += &comment(f.doc.as_deref(), "\t");
                s += &format!("\t{};\n", field(f, model));
            }
            s + "}"
        }
        Shape::Union(members) if members.iter().any(|m| matches!(m, Shape::Object(_))) => {
            let tag = Shape::discriminator(members);
            members
                .iter()
                .map(|m| tag.as_deref().map_or(m.clone(), |tag| m.tag_first(tag)))
                .map(|m| format!("\n\t| {}", expr(&m, model)))
                .collect()
        }
        other => expr(other, model),
    }
}

fn expr(shape: &Shape, model: &Model) -> String {
    match shape {
        Shape::Any => "unknown".into(),
        Shape::Null => "null".into(),
        Shape::Bool => "boolean".into(),
        Shape::Int | Shape::Float => "number".into(),
        Shape::Str => "string".into(),
        Shape::Literal(v) => literal(v),
        Shape::Array(inner) => format!("{}[]", grouped(inner, model)),
        Shape::Tuple(items) => format!(
            "[{}]",
            items
                .iter()
                .map(|i| expr(i, model))
                .collect::<Vec<_>>()
                .join(", ")
        ),
        Shape::Map(values) => format!("Record<string, {}>", expr(values, model)),
        Shape::Object(fields) if fields.is_empty() => "Record<string, never>".into(),
        Shape::Object(fields) => format!(
            "{{ {} }}",
            fields
                .iter()
                .map(|f| field(f, model))
                .collect::<Vec<_>>()
                .join("; ")
        ),
        Shape::Union(members) => members
            .iter()
            .map(|m| expr(m, model))
            .collect::<Vec<_>>()
            .join(" | "),
        Shape::Intersection(members) => members
            .iter()
            .map(|m| grouped(m, model))
            .collect::<Vec<_>>()
            .join(" & "),
        Shape::Ref(id) => model.types[*id].name.clone(),
    }
}

/// `expr`, parenthesized where a postfix `[]` or an `&` would bind tighter than its `|`.
fn grouped(shape: &Shape, model: &Model) -> String {
    match shape {
        Shape::Union(_) | Shape::Intersection(_) => format!("({})", expr(shape, model)),
        other => expr(other, model),
    }
}

fn field(f: &Field, model: &Model) -> String {
    let opt = if f.required { "" } else { "?" };
    format!("{}{opt}: {}", key(&f.key), expr(&f.shape, model))
}

fn key(k: &str) -> String {
    let mut chars = k.chars();
    let ident = chars
        .next()
        .is_some_and(|c| c.is_ascii_alphabetic() || c == '_' || c == '$')
        && chars.all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '$');
    match ident {
        true => k.into(),
        false => quoted(k),
    }
}

fn literal(v: &Value) -> String {
    match v {
        Value::String(s) => quoted(s),
        other => other.to_string(),
    }
}

fn quoted(s: &str) -> String {
    format!("'{}'", s.replace('\\', "\\\\").replace('\'', "\\'"))
}

fn comment(doc: Option<&str>, indent: &str) -> String {
    doc.map(|d| {
        d.lines()
            .map(|l| format!("{indent}// {l}\n").replace(" \n", "\n"))
            .collect()
    })
    .unwrap_or_default()
}

fn relative_import(from_module: &str, to_module: &str) -> String {
    let from: Vec<&str> = from_module.split("::").collect();
    let to: Vec<&str> = to_module.split("::").collect();
    let from_dir = &from[..from.len() - 1];
    let common = from_dir.iter().zip(&to).take_while(|(a, b)| a == b).count();
    let ups = from_dir.len() - common;
    let rest = to[common..].join("/");
    match ups {
        0 => format!("./{rest}"),
        n => format!("{}{rest}", "../".repeat(n)),
    }
}
