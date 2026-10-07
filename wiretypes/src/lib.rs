//! Rust types as the single source for their TypeScript and Python definitions.
//!
//! `#[wire]` on a struct, enum or generic-instantiating type alias derives `JsonSchema` and
//! registers the type; on a `const` or `static` it registers the value. [`sync`] renders every
//! registered type and value into the targets a TOML config names, one file per Rust module,
//! and either writes them or checks the committed ones.

extern crate self as wiretypes;

pub use inventory;
pub use schemars;
pub use serde_json;
pub use wiretypes_macro::wire;

pub use error::Error;

use std::path::Path;

use schemars::{generate::SchemaGenerator, JsonSchema, Schema};

pub const WRITE_ENV: &str = "WIRETYPES";

inventory::collect!(WireType);
inventory::collect!(WireConst);

/// One `#[wire]` registration; built by the macro through [`registration`].
pub struct WireType {
    pub module: &'static str,
    pub name: &'static str,
    pub line: u32,
    pub contract: Contract,
    pub subschema: fn(&mut SchemaGenerator) -> Schema,
}

/// One `#[wire]` const or static: its value, serialized when the targets are rendered.
pub struct WireConst {
    pub module: &'static str,
    pub name: &'static str,
    pub line: u32,
    /// The item's `///` lines, empty for none.
    pub doc: &'static str,
    pub value: fn() -> serde_json::Result<serde_json::Value>,
}

/// Which side of serde the generated type describes: what Rust sends, or what it accepts.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Contract {
    Serialize,
    Deserialize,
}

/// Implemented by `#[wire]` for every annotated struct and enum; a type alias registers
/// through it.
pub trait Wire: JsonSchema {
    const CONTRACT: Contract;
}

pub const fn registration<T: Wire>(
    module: &'static str,
    name: &'static str,
    line: u32,
) -> WireType {
    WireType {
        module,
        name,
        line,
        contract: T::CONTRACT,
        subschema: subschema::<T>,
    }
}

/// A map alias's registration: a map is spelled inline wherever it is used, so its contract only
/// picks the generator its value types are read from, and each of those is emitted under its own.
pub const fn map_registration<T: JsonSchema>(
    module: &'static str,
    name: &'static str,
    line: u32,
) -> WireType {
    WireType {
        module,
        name,
        line,
        contract: Contract::Serialize,
        subschema: subschema::<T>,
    }
}

/// Field transform `#[wire]` adds under `skip_serializing_if = "Option::is_none"`: such a field
/// is absent rather than null.
pub fn never_null(schema: &mut Schema) {
    let Some(obj) = schema.as_object_mut() else {
        return;
    };
    if let Some(serde_json::Value::Array(types)) = obj.get_mut("type") {
        types.retain(|t| t != "null");
        if let [only] = types.as_slice() {
            let only = only.clone();
            obj.insert("type".into(), only);
        }
    }
    if let Some(serde_json::Value::Array(members)) = obj.get("anyOf") {
        let kept: Vec<_> = members
            .iter()
            .filter(|m| m.get("type").and_then(|t| t.as_str()) != Some("null"))
            .cloned()
            .collect();
        match kept.as_slice() {
            [serde_json::Value::Object(only)] => {
                let only = only.clone();
                obj.remove("anyOf");
                obj.extend(only);
            }
            _ => {
                obj.insert("anyOf".into(), kept.into());
            }
        }
    }
}

/// Renders every registered type into the targets of the config at `config_path`. Writes them
/// when the `WIRETYPES` env var is `write`, otherwise fails with the files that differ.
pub fn sync(config_path: impl AsRef<Path>) -> Result<(), Error> {
    let config_path = config_path.as_ref();
    let config = config::Config::load(config_path)?;
    let model = model::Model::collect(
        inventory::iter::<WireType>(),
        inventory::iter::<WireConst>(),
    )?;
    let root = config_path.parent().unwrap_or(Path::new("."));
    let outputs = config.render(&model)?;
    match std::env::var(WRITE_ENV).as_deref() {
        Ok("write") => output::write(root, &outputs),
        _ => output::check(root, &outputs, &config.regenerate),
    }
}

fn subschema<T: JsonSchema>(generator: &mut SchemaGenerator) -> Schema {
    generator.subschema_for::<T>()
}

mod config;
mod error;
mod model;
mod output;
mod python;
mod shape;
mod ts;

#[cfg(test)]
mod tests;
