use std::collections::{BTreeMap, HashMap};

use schemars::generate::{SchemaGenerator, SchemaSettings};
use serde_json::Value;

use crate::{
    error::Error,
    shape::{self, Shape, TypeId},
    Contract, WireConst, WireType,
};

/// Every registered type, reduced to shapes, and every registered value, each in (module, source
/// line) order.
pub struct Model {
    pub types: Vec<TypeDef>,
    pub consts: Vec<ConstDef>,
}

pub struct TypeDef {
    /// `crate::module::path` the type is declared in.
    pub module: String,
    pub name: String,
    pub doc: Option<String>,
    pub shape: Shape,
}

pub struct ConstDef {
    pub module: String,
    pub name: String,
    pub doc: Option<String>,
    pub value: Value,
    /// The value's type when it is a registered one, which the targets annotate it with.
    pub ty: Option<TypeId>,
}

/// Every module path with what its file holds.
pub type Modules<'a> = BTreeMap<&'a str, Module<'a>>;

/// What one output file holds: a module's values, then its types.
#[derive(Default)]
pub struct Module<'a> {
    pub consts: Vec<&'a ConstDef>,
    pub types: Vec<TypeId>,
}

/// One schema generator's output: each registration's and each value's schema there, and the
/// registration every `$defs` name stands for.
struct Generated {
    defs: serde_json::Map<String, Value>,
    roots: Vec<Value>,
    value_roots: Vec<Value>,
    by_def: HashMap<String, TypeId>,
}

impl Model {
    pub fn collect<'a>(
        registry: impl IntoIterator<Item = &'a WireType>,
        values: impl IntoIterator<Item = &'a WireConst>,
    ) -> Result<Self, Error> {
        let mut regs: Vec<&WireType> = registry.into_iter().collect();
        regs.sort_by_key(|r| (r.module, r.line, r.name));
        for pair in regs.windows(2) {
            if (pair[0].module, pair[0].name) == (pair[1].module, pair[1].name) {
                return Err(Error::Duplicate {
                    module: pair[0].module.into(),
                    name: pair[0].name.into(),
                });
            }
        }
        let mut values: Vec<&WireConst> = values.into_iter().collect();
        values.sort_by_key(|c| (c.module, c.line, c.name));
        let ser = Generated::new(
            &regs,
            &values,
            SchemaSettings::draft2020_12().for_serialize(),
        );
        let de = Generated::new(&regs, &[], SchemaSettings::draft2020_12().for_deserialize());
        let types = regs
            .iter()
            .enumerate()
            .map(|(id, reg)| {
                let generated = match reg.contract {
                    Contract::Serialize => &ser,
                    Contract::Deserialize => &de,
                };
                generated.type_def(id, reg)
            })
            .collect::<Result<_, _>>()?;
        let consts = values
            .into_iter()
            .zip(&ser.value_roots)
            .map(|(c, root)| {
                let value = (c.value)().map_err(|e| Error::Value {
                    owner: format!("{}::{}", c.module, c.name),
                    reason: e.to_string(),
                })?;
                Ok(ConstDef {
                    module: c.module.into(),
                    name: c.name.into(),
                    doc: (!c.doc.is_empty()).then(|| c.doc.into()),
                    value,
                    ty: def_name(root).and_then(|def| ser.by_def.get(&def).copied()),
                })
            })
            .collect::<Result<_, Error>>()?;
        Ok(Self { types, consts })
    }

    /// Each module's values and type ids, in declaration order.
    pub fn modules(&self) -> Modules<'_> {
        let mut out = Modules::new();
        for c in &self.consts {
            out.entry(c.module.as_str()).or_default().consts.push(c);
        }
        for (id, t) in self.types.iter().enumerate() {
            out.entry(t.module.as_str()).or_default().types.push(id);
        }
        out
    }
}

impl Generated {
    fn new(regs: &[&WireType], values: &[&WireConst], settings: SchemaSettings) -> Self {
        let mut generator = SchemaGenerator::new(settings);
        let roots: Vec<Value> = regs
            .iter()
            .map(|r| (r.subschema)(&mut generator).to_value())
            .collect();
        let value_roots = values
            .iter()
            .map(|c| (c.schema)(&mut generator).to_value())
            .collect();
        let by_def = roots
            .iter()
            .enumerate()
            .filter_map(|(id, root)| Some((def_name(root)?, id)))
            .collect();
        Self {
            defs: generator.take_definitions(true),
            roots,
            value_roots,
            by_def,
        }
    }

    fn type_def(&self, id: TypeId, reg: &WireType) -> Result<TypeDef, Error> {
        let owner = format!("{}::{}", reg.module, reg.name);
        // an inlined type (`#[schemars(inline)]`, a transparent newtype) has no definition
        let schema = match def_name(&self.roots[id]) {
            Some(def) => &self.defs[&def],
            None => &self.roots[id],
        };
        let resolve = |def: &str| {
            self.by_def
                .get(def)
                .copied()
                .ok_or_else(|| Error::Unregistered {
                    def: def.into(),
                    owner: owner.clone(),
                })
        };
        Ok(TypeDef {
            module: reg.module.into(),
            name: reg.name.into(),
            doc: shape::doc(schema),
            shape: shape::from_schema(schema, &owner, &resolve)?,
        })
    }
}

fn def_name(root: &Value) -> Option<String> {
    let obj = root.as_object()?;
    let name = obj.get("$ref")?.as_str()?.strip_prefix("#/$defs/")?;
    (obj.len() == 1).then(|| shape::decode_ref(name))
}
