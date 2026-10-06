use std::collections::BTreeSet;

use serde_json::{Map, Value};

use crate::error::Error;

/// Index of a registered type in [`crate::model::Model::types`].
pub type TypeId = usize;

/// A field of an object shape; fields are ordered by key.
#[derive(Clone, Debug, PartialEq)]
pub struct Field {
    pub key: String,
    pub shape: Shape,
    pub required: bool,
    pub doc: Option<String>,
}

/// The language-neutral form a JSON Schema reduces to, the one thing the emitters read.
#[derive(Clone, Debug, PartialEq)]
pub enum Shape {
    Any,
    Null,
    Bool,
    Int,
    Float,
    Str,
    Literal(Value),
    Array(Box<Shape>),
    Tuple(Vec<Shape>),
    /// A JSON object keyed by arbitrary strings.
    Map(Box<Shape>),
    Object(Vec<Field>),
    Union(Vec<Shape>),
    Intersection(Vec<Shape>),
    Ref(TypeId),
}

impl Shape {
    pub fn is_null(&self) -> bool {
        matches!(self, Self::Null)
    }

    /// Adds every type this shape references to `out`.
    pub fn refs(&self, out: &mut BTreeSet<TypeId>) {
        match self {
            Self::Ref(id) => {
                out.insert(*id);
            }
            Self::Array(inner) | Self::Map(inner) => inner.refs(out),
            Self::Tuple(items) | Self::Union(items) | Self::Intersection(items) => {
                items.iter().for_each(|i| i.refs(out))
            }
            Self::Object(fields) => fields.iter().for_each(|f| f.shape.refs(out)),
            _ => {}
        }
    }

    /// The key every object member of a union carries as a distinct string literal, if any.
    pub fn discriminator(members: &[Shape]) -> Option<String> {
        let objects: Vec<&Vec<Field>> = members
            .iter()
            .filter_map(|m| match m {
                Self::Object(fields) => Some(fields),
                _ => None,
            })
            .collect();
        let first = objects.first()?;
        first
            .iter()
            .filter(|f| matches!(f.shape, Self::Literal(Value::String(_))))
            .map(|f| &f.key)
            .find(|key| {
                objects.iter().all(|fields| {
                    fields.iter().any(|f| {
                        &f.key == *key && matches!(f.shape, Self::Literal(Value::String(_)))
                    })
                })
            })
            .cloned()
    }

    /// This shape with an object's `tag` field moved to the front, as a union variant reads.
    pub fn tag_first(&self, tag: &str) -> Shape {
        match self {
            Self::Object(fields) => {
                let mut fields = fields.clone();
                fields.sort_by_key(|f| f.key != tag);
                Self::Object(fields)
            }
            other => other.clone(),
        }
    }

    fn union(members: Vec<Shape>) -> Shape {
        let mut flat: Vec<Shape> = Vec::new();
        for m in members {
            let parts = match m {
                Self::Union(inner) => inner,
                other => vec![other],
            };
            for p in parts {
                if !flat.contains(&p) {
                    flat.push(p);
                }
            }
        }
        if flat.contains(&Self::Any) {
            return Self::Any;
        }
        // null last, as both emitters spell an optional value `T | null`
        flat.sort_by_key(Shape::is_null);
        match flat.len() {
            1 => flat.pop().unwrap(),
            _ => Self::Union(flat),
        }
    }

    fn intersection(members: Vec<Shape>) -> Shape {
        let mut kept: Vec<Shape> = members.into_iter().filter(|m| *m != Self::Any).collect();
        match kept.len() {
            0 => Self::Any,
            1 => kept.pop().unwrap(),
            _ => Self::Intersection(kept),
        }
    }
}

/// Reduces `schema` to a [`Shape`]; `resolve` maps a `$defs` name to its registered type.
pub fn from_schema(
    schema: &Value,
    owner: &str,
    resolve: &dyn Fn(&str) -> Result<TypeId, Error>,
) -> Result<Shape, Error> {
    let obj = match schema {
        Value::Bool(true) => return Ok(Shape::Any),
        Value::Object(obj) => obj,
        _ => return Err(unsupported(owner, schema)),
    };
    let sub = |s: &Value| from_schema(s, owner, resolve);
    let subs = |key: &str| -> Result<Option<Vec<Shape>>, Error> {
        obj.get(key)
            .map(|v| {
                v.as_array()
                    .ok_or_else(|| unsupported(owner, v))?
                    .iter()
                    .map(sub)
                    .collect()
            })
            .transpose()
    };

    if let Some(r) = obj.get("$ref") {
        let name = r
            .as_str()
            .and_then(|r| r.strip_prefix("#/$defs/"))
            .ok_or_else(|| unsupported(owner, r))?;
        return Ok(Shape::Ref(resolve(&decode_ref(name))?));
    }
    if let Some(c) = obj.get("const") {
        return Ok(Shape::Literal(c.clone()));
    }
    if let Some(Value::Array(values)) = obj.get("enum") {
        return Ok(Shape::union(
            values.iter().cloned().map(Shape::Literal).collect(),
        ));
    }

    let mut facets = Vec::new();
    if let Some(types) = obj.get("type") {
        let types: Vec<&str> = match types {
            Value::String(t) => vec![t.as_str()],
            Value::Array(ts) => ts.iter().filter_map(Value::as_str).collect(),
            _ => return Err(unsupported(owner, types)),
        };
        let typed = types
            .into_iter()
            .map(|t| typed_shape(t, obj, owner, &sub))
            .collect::<Result<Vec<_>, _>>()?;
        facets.push(Shape::union(typed));
    }
    let combined = [subs("anyOf")?, subs("oneOf")?]
        .into_iter()
        .flatten()
        .map(Shape::union);
    for union in combined {
        // a bare `type: object` beside the variants only restates them
        if facets.first() == Some(&Shape::Map(Box::new(Shape::Any))) {
            facets.clear();
        }
        facets.push(union);
    }
    if let Some(all) = subs("allOf")? {
        facets.extend(all);
    }
    Ok(Shape::intersection(facets))
}

pub fn doc(schema: &Value) -> Option<String> {
    schema
        .get("description")
        .and_then(Value::as_str)
        .map(str::to_string)
}

/// Undoes the JSON Pointer and percent encoding schemars applies to a `$defs` name in a `$ref`.
pub fn decode_ref(name: &str) -> String {
    let bytes = name.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        let hex = bytes
            .get(i + 1..i + 3)
            .and_then(|h| std::str::from_utf8(h).ok());
        match (bytes[i], hex.and_then(|h| u8::from_str_radix(h, 16).ok())) {
            (b'%', Some(byte)) => {
                out.push(byte);
                i += 3;
            }
            (b, _) => {
                out.push(b);
                i += 1;
            }
        }
    }
    String::from_utf8_lossy(&out)
        .replace("~1", "/")
        .replace("~0", "~")
}

fn typed_shape(
    t: &str,
    obj: &Map<String, Value>,
    owner: &str,
    sub: &dyn Fn(&Value) -> Result<Shape, Error>,
) -> Result<Shape, Error> {
    Ok(match t {
        "null" => Shape::Null,
        "boolean" => Shape::Bool,
        "integer" => Shape::Int,
        "number" => Shape::Float,
        "string" => Shape::Str,
        "array" => match (obj.get("prefixItems"), obj.get("items")) {
            (Some(Value::Array(items)), _) => {
                Shape::Tuple(items.iter().map(sub).collect::<Result<_, _>>()?)
            }
            (_, Some(items)) => Shape::Array(Box::new(sub(items)?)),
            _ => Shape::Array(Box::new(Shape::Any)),
        },
        "object" => object_shape(obj, owner, sub)?,
        _ => return Err(unsupported(owner, &Value::String(t.into()))),
    })
}

fn object_shape(
    obj: &Map<String, Value>,
    owner: &str,
    sub: &dyn Fn(&Value) -> Result<Shape, Error>,
) -> Result<Shape, Error> {
    let required: Vec<&str> = obj
        .get("required")
        .and_then(Value::as_array)
        .map(|r| r.iter().filter_map(Value::as_str).collect())
        .unwrap_or_default();
    let mut fields = Vec::new();
    if let Some(Value::Object(props)) = obj.get("properties") {
        for (key, schema) in props {
            fields.push(Field {
                key: key.clone(),
                shape: sub(schema)?,
                required: required.contains(&key.as_str()),
                doc: doc(schema),
            });
        }
        fields.sort_by(|a, b| a.key.cmp(&b.key));
    }
    let values = match (
        obj.get("patternProperties"),
        obj.get("additionalProperties"),
    ) {
        (Some(Value::Object(patterns)), _) => match patterns.values().collect::<Vec<_>>()[..] {
            [only] => Some(sub(only)?),
            _ => return Err(unsupported(owner, &Value::Object(patterns.clone()))),
        },
        (Some(other), _) => return Err(unsupported(owner, other)),
        (None, Some(Value::Bool(false))) | (None, None) => None,
        (None, Some(schema)) => Some(sub(schema)?),
    };
    Ok(match (fields.is_empty(), values) {
        (true, Some(v)) => Shape::Map(Box::new(v)),
        (true, None) if !obj.contains_key("properties") => Shape::Map(Box::new(Shape::Any)),
        (_, None) => Shape::Object(fields),
        (false, Some(v)) => {
            Shape::Intersection(vec![Shape::Object(fields), Shape::Map(Box::new(v))])
        }
    })
}

fn unsupported(owner: &str, schema: &Value) -> Error {
    Error::Unsupported {
        owner: owner.to_string(),
        schema: schema.to_string(),
    }
}
