use std::{fmt, io, path::PathBuf};

#[derive(Debug)]
pub enum Error {
    Io(PathBuf, io::Error),
    Config(PathBuf, toml::de::Error),
    /// Two registrations under one module and name.
    Duplicate {
        module: String,
        name: String,
    },
    /// A type reached through a registered one carries a schema but no `#[wire]`.
    Unregistered {
        def: String,
        owner: String,
    },
    /// A schema construct no emitter renders.
    Unsupported {
        owner: String,
        schema: String,
    },
    /// One output file would declare or import a name twice.
    Collision {
        file: String,
        name: String,
    },
    /// A key the dataclass style cannot spell as a field.
    PythonField {
        owner: String,
        key: String,
    },
    /// Committed outputs that differ from the rendered ones, and the command that rewrites them.
    Drift {
        files: Vec<String>,
        regenerate: String,
    },
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            Self::Io(path, e) => write!(f, "{}: {e}", path.display()),
            Self::Config(path, e) => write!(f, "{}: {e}", path.display()),
            Self::Duplicate { module, name } => write!(f, "`{module}::{name}` is registered twice"),
            Self::Unregistered { def, owner } => write!(
                f,
                "`{owner}` reaches the schema `{def}`, whose type has no #[wire]"
            ),
            Self::Unsupported { owner, schema } => {
                write!(f, "`{owner}`: no emitter renders the schema {schema}")
            }
            Self::Collision { file, name } => write!(f, "{file}: `{name}` is declared twice"),
            Self::PythonField { owner, key } => write!(
                f,
                "`{owner}`: key `{key}` is not a Python identifier, which the dataclass style needs"
            ),
            Self::Drift { files, regenerate } => write!(
                f,
                "generated types are stale, run `{regenerate}`:\n  {}",
                files.join("\n  ")
            ),
        }
    }
}

impl std::error::Error for Error {}
