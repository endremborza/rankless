use std::{collections::BTreeMap, path::Path};

use serde::Deserialize;

use crate::{error::Error, model::Model, python, ts};

/// Rendered files per output directory, paths relative to the config's directory.
pub type Outputs = BTreeMap<String, BTreeMap<String, String>>;

/// The whole of a `wiretypes.toml`: where each target writes and how. Paths are relative to the
/// file's directory.
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Config {
    /// The command that rewrites the outputs, named in their headers and in the drift error.
    #[serde(default = "default_regenerate")]
    pub regenerate: String,
    pub ts: Option<TsTarget>,
    pub python: Option<PythonTarget>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TsTarget {
    pub out: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PythonTarget {
    pub out: String,
    #[serde(default)]
    pub style: PythonStyle,
}

#[derive(Deserialize, Default, Clone, Copy, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum PythonStyle {
    #[default]
    TypedDict,
    Dataclass,
}

impl Config {
    pub fn load(path: &Path) -> Result<Self, Error> {
        let text = std::fs::read_to_string(path).map_err(|e| Error::Io(path.into(), e))?;
        toml::from_str(&text).map_err(|e| Error::Config(path.into(), e))
    }

    pub fn render(&self, model: &Model) -> Result<Outputs, Error> {
        let mut out = Outputs::new();
        if let Some(t) = &self.ts {
            out.insert(t.out.clone(), ts::render(model, &self.regenerate)?);
        }
        if let Some(t) = &self.python {
            out.insert(
                t.out.clone(),
                python::render(model, t.style, &self.regenerate)?,
            );
        }
        Ok(out)
    }
}

fn default_regenerate() -> String {
    format!("{}=write cargo test", crate::WRITE_ENV)
}
