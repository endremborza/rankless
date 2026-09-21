//! Binding and evaluation of the table's expressions against one root type: a call becomes a
//! metric with a resolved argument and its kind for the root, a `where` tree becomes a predicate
//! over dm ids, and a cohort is the root's entities that pass it, in the order of a sort call.

use std::cmp::Ordering;
use std::sync::Arc;

use dmove::Entity;
use hashbrown::HashMap;
use rankless_expr::{Arg as Word, Call, Expr, Op, Operand};
use rankless_rs::gen::a1_entity_mapping::Cities;
use rankless_trees::{
    interfacing::{Getters, RootColumns},
    io::TreeSpecs,
    metrics::{self, Arg, Cost, Kind, MetricDecl, Param, Value, ValueType, METRICS},
    AttributeLabelUnion,
};

use crate::consts::SCREEN_K;
use crate::responses::TableRow;
use crate::state::{order_keyed, NameState, NameStateMap, StatesT};

// Why an expression will not bind to this root. Always a 400 with the reason: the root itself
// exists by the time anything binds, since `Ctx::new` is what reports an unknown root type.
pub(crate) struct Reject(pub String);

// Everything a root type's expressions bind against.
#[derive(Clone, Copy)]
pub(crate) struct Ctx<'a> {
    pub etype: &'a str,
    pub state: &'a NameState,
    pub cols: &'a RootColumns,
    pub gets: &'a Getters,
    pub ns: &'a NameStateMap,
    pub satts: &'a AttributeLabelUnion,
    pub specs: &'a TreeSpecs,
}

// A call bound to the root: the metric, its resolved argument, its kind here, and the canonical
// text of the two — the key its column carries. Shared, because every row of a page repeats it.
#[derive(Clone)]
pub(crate) struct BoundCall {
    pub decl: &'static MetricDecl,
    pub arg: Arg,
    pub kind: Kind,
    pub key: Arc<str>,
}

pub(crate) enum Bound {
    Clause(BoundClause),
    And(Vec<Bound>),
    Or(Vec<Bound>),
    Not(Box<Bound>),
}

pub(crate) struct BoundClause {
    call: BoundCall,
    op: Op,
    operand: BoundOperand,
}

enum BoundOperand {
    Nums(Vec<f64>),
    Ids(Vec<u32>),
}

pub(crate) struct Cohort<'a> {
    ctx: Ctx<'a>,
    sort: BoundCall,
    filter: Option<Bound>,
    rids: Rids<'a>,
    // Entities passing the global clauses.
    pub total: usize,
    // An intricate sort or clause: only the top SCREEN_K of `total` by citations are ranked.
    pub screened: bool,
    // The metric columns the rows carry.
    pub columns: Vec<BoundCall>,
}

// Response ids in one cohort ordering: the citation order is the response array itself, the other
// startup orderings are precomputed, a narrowed, screened or parameterized ordering is scanned per
// request and kept with the values it was ordered by.
enum Rids<'a> {
    Identity(usize),
    Fixed(&'a [u32]),
    Keyed(Box<[u32]>, Box<[f64]>),
}

impl From<String> for Reject {
    fn from(msg: String) -> Self {
        Self(msg)
    }
}

impl From<&str> for Reject {
    fn from(msg: &str) -> Self {
        Self(msg.to_string())
    }
}

impl<'a> Ctx<'a> {
    pub fn new(states: &'a StatesT, etype: &'a str) -> Option<Self> {
        let (ns, satts, tm) = &states.0;
        Some(Self {
            etype,
            state: ns.get(etype)?,
            cols: tm.state.gets.columns_for(etype)?,
            gets: &tm.state.gets,
            ns,
            satts,
            specs: &tm.specs,
        })
    }

    pub fn kind(&self, decl: &MetricDecl) -> Option<Kind> {
        decl.kind(self.cols, |level| self.specs.has_level(self.etype, level))
    }

    // The root's registry: every metric that exists for it, with its kind.
    pub fn registry(&self) -> impl Iterator<Item = (&'static MetricDecl, Kind)> + '_ {
        METRICS.iter().filter_map(|m| self.kind(m).map(|k| (m, k)))
    }

    // An entity of a type by semantic id, else by name (case-insensitive); cities have names only.
    // The empty name resolves to nothing: every label array carries a blank slot 0 for the null id,
    // which a case-insensitive match on "" would otherwise hit.
    pub fn resolve(&self, entity: &str, name: &str) -> Option<u32> {
        if name.is_empty() {
            return None;
        }
        if entity == Cities::NAME {
            return (1..Cities::N)
                .find(|&cid| self.gets.cinames(cid).eq_ignore_ascii_case(name.as_bytes()))
                .map(|cid| cid as u32);
        }
        if let Some(dm) = self.ns.get(entity).and_then(|s| s.sem_to_dm.get(name)) {
            return Some(*dm);
        }
        self.satts
            .get(entity)?
            .iter()
            .position(|l| l.name.eq_ignore_ascii_case(name))
            .map(|dm| dm as u32)
    }

    // The key a column carries: the bound call printed by `Call`'s own `Display`, so a semantic id
    // and a label naming the same entity produce one column, not two, and the key parses back into
    // the call it names.
    fn canonical_key(&self, decl: &MetricDecl, arg: Arg) -> Arc<str> {
        let sem = |p: Param, dm: usize| {
            let entity = p.entity().expect("a slug parameter names an entity");
            let id = self
                .satts
                .get(entity)
                .and_then(|labels| labels.get(dm))
                .map_or_else(|| dm.to_string(), |l| l.semantic_id.to_string());
            Word::Name(id)
        };
        let args = match arg {
            Arg::Subfield(dm) => vec![sem(Param::Subfield, dm)],
            Arg::Country(dm) => vec![sem(Param::Country, dm)],
            Arg::Window(Some(from), Some(to)) => {
                vec![Word::Num(from as f64), Word::Num(to as f64)]
            }
            Arg::None | Arg::Window(..) => Vec::new(),
        };
        Call {
            metric: decl.id.to_string(),
            args,
        }
        .to_string()
        .into()
    }

    pub fn bind_call(&self, call: &Call) -> Result<BoundCall, Reject> {
        let decl = metrics::metric(&call.metric)
            .ok_or_else(|| format!("unknown metric {}", call.metric))?;
        let kind = self
            .kind(decl)
            .ok_or_else(|| format!("{} does not exist for {}", decl.id, self.etype))?;
        let arg = match (decl.param, call.args.as_slice()) {
            (None, []) => Arg::None,
            (None, _) => return Err(format!("{} takes no argument", decl.id).into()),
            (Some(Param::Window), [Word::Num(from), Word::Num(to)]) => {
                Arg::Window(Some(year(*from)?), Some(year(*to)?))
            }
            (Some(Param::Window), _) => {
                return Err(format!("{} takes a year window: (from, to)", decl.id).into())
            }
            (Some(p), [Word::Name(name)]) => {
                let entity = p.entity().expect("a slug parameter names an entity");
                let id = self
                    .resolve(entity, name)
                    .ok_or_else(|| unknown(entity, name))?;
                match p {
                    Param::Subfield => Arg::Subfield(id as usize),
                    Param::Country => Arg::Country(id as usize),
                    Param::Window => unreachable!(),
                }
            }
            (Some(p), _) => {
                return Err(
                    format!("{} takes one {}", decl.id, p.entity().unwrap_or("value")).into(),
                )
            }
        };
        Ok(BoundCall {
            decl,
            arg,
            kind,
            key: self.canonical_key(decl, arg),
        })
    }

    pub fn bind_where(&self, e: &Expr) -> Result<Bound, Reject> {
        Ok(match e {
            Expr::Clause(c) => {
                let call = self.bind_call(&c.call)?;
                if call.decl.cost == Cost::Walk {
                    return Err(format!(
                        "{} is computed per entity by a tree walk: a page column, not a clause",
                        call.decl.id
                    )
                    .into());
                }
                let operand = match (call.decl.value, &c.operand) {
                    (ValueType::Entity(entity) | ValueType::Entities(entity), operand) => {
                        if !matches!(c.op, Op::Eq | Op::Ne | Op::In | Op::NotIn) {
                            return Err(
                                format!("{} takes =, !=, in or not in", call.decl.id).into()
                            );
                        }
                        let names: Vec<&str> = match operand {
                            Operand::Name(n) => vec![n.as_str()],
                            Operand::List(items) => {
                                items.iter().map(word_name).collect::<Result<_, _>>()?
                            }
                            Operand::Num(_) => {
                                return Err(format!("{} compares to a name", call.decl.id).into())
                            }
                        };
                        let ids = names
                            .iter()
                            .map(|n| self.resolve(entity, n).ok_or_else(|| unknown(entity, n)))
                            .collect::<Result<Vec<u32>, _>>()?;
                        BoundOperand::Ids(ids)
                    }
                    (_, Operand::Num(n)) => BoundOperand::Nums(vec![*n]),
                    (_, Operand::List(items)) if c.op.is_membership() => BoundOperand::Nums(
                        items
                            .iter()
                            .map(|w| match w {
                                Word::Num(n) => Ok(*n),
                                Word::Name(_) => Err(Reject::from(format!(
                                    "{} compares to numbers",
                                    call.decl.id
                                ))),
                            })
                            .collect::<Result<_, _>>()?,
                    ),
                    _ => return Err(format!("{} compares to a number", call.decl.id).into()),
                };
                Bound::Clause(BoundClause {
                    call,
                    op: c.op,
                    operand,
                })
            }
            Expr::And(items) => Bound::And(self.bind_all(items)?),
            Expr::Or(items) => Bound::Or(self.bind_all(items)?),
            Expr::Not(inner) => Bound::Not(Box::new(self.bind_where(inner)?)),
        })
    }

    fn bind_all(&self, items: &[Expr]) -> Result<Vec<Bound>, Reject> {
        items.iter().map(|e| self.bind_where(e)).collect()
    }

    pub fn read(&self, call: &BoundCall, dm: usize) -> Option<Value> {
        call.decl.read(self.cols, self.gets, dm, call.arg)
    }

    pub fn num(&self, call: &BoundCall, dm: usize) -> Option<f64> {
        match self.read(call, dm)? {
            Value::Num(v) => Some(v),
            _ => None,
        }
    }

    fn dm(&self, rid: u32) -> usize {
        self.state.responses[rid as usize].dm_id
    }
}

impl BoundClause {
    fn admits(&self, ctx: &Ctx, dm: usize) -> bool {
        let Some(value) = ctx.read(&self.call, dm) else {
            return false;
        };
        match (&self.operand, value) {
            (BoundOperand::Nums(ns), Value::Num(v)) => match self.op {
                Op::Eq => ns.iter().any(|n| *n == v),
                Op::Ne => ns.iter().all(|n| *n != v),
                Op::Lt => v < ns[0],
                Op::Le => v <= ns[0],
                Op::Gt => v > ns[0],
                Op::Ge => v >= ns[0],
                Op::In => ns.contains(&v),
                Op::NotIn => !ns.contains(&v),
            },
            (BoundOperand::Ids(ids), Value::Id(id)) => match self.op {
                Op::Eq | Op::In => ids.contains(&id),
                _ => !ids.contains(&id),
            },
            // A set-valued read matches when any of its values does, and excludes when none does.
            (BoundOperand::Ids(ids), Value::Ids(mine)) => {
                let any = mine.iter().any(|m| *m != 0 && ids.contains(m));
                match self.op {
                    Op::Eq | Op::In => any,
                    _ => !any,
                }
            }
            _ => false,
        }
    }
}

impl Bound {
    pub fn admits(&self, ctx: &Ctx, dm: usize) -> bool {
        match self {
            Self::Clause(c) => c.admits(ctx, dm),
            Self::And(items) => items.iter().all(|b| b.admits(ctx, dm)),
            Self::Or(items) => items.iter().any(|b| b.admits(ctx, dm)),
            Self::Not(inner) => !inner.admits(ctx, dm),
        }
    }

    pub fn calls(&self) -> Vec<&BoundCall> {
        match self {
            Self::Clause(c) => vec![&c.call],
            Self::And(items) | Self::Or(items) => items.iter().flat_map(|b| b.calls()).collect(),
            Self::Not(inner) => inner.calls(),
        }
    }

    fn is_intricate(&self) -> bool {
        self.calls().iter().any(|c| c.kind == Kind::Intricate)
    }

    // The global and the intricate parts of a top-level conjunction: the global ones narrow the
    // cohort before the screen, the intricate ones apply to the screened set. An intricate clause
    // under `or` or `not` cannot be split off and is refused.
    fn split(self) -> Result<(Option<Bound>, Option<Bound>), Reject> {
        let items = match self {
            Self::And(items) => items,
            other => vec![other],
        };
        let (mut global, mut intricate) = (Vec::new(), Vec::new());
        for b in items {
            if !b.is_intricate() {
                global.push(b);
            } else if matches!(b, Self::Clause(_)) {
                intricate.push(b);
            } else {
                return Err(
                    "a clause on a per-entity metric applies after the screen, so it combines only with and at the top level"
                        .into(),
                );
            }
        }
        let wrap = |mut v: Vec<Bound>| match v.len() {
            0 => None,
            1 => v.pop(),
            _ => Some(Bound::And(v)),
        };
        Ok((wrap(global), wrap(intricate)))
    }
}

impl Rids<'_> {
    fn len(&self) -> usize {
        match self {
            Self::Identity(n) => *n,
            Self::Fixed(s) => s.len(),
            Self::Keyed(v, _) => v.len(),
        }
    }

    fn at(&self, pos: usize) -> u32 {
        match self {
            Self::Identity(_) => pos as u32,
            Self::Fixed(s) => s[pos],
            Self::Keyed(v, _) => v[pos],
        }
    }
}

impl<'a> Cohort<'a> {
    pub fn new(ctx: Ctx<'a>, sort: BoundCall, filter: Option<Bound>) -> Result<Self, Reject> {
        if sort.decl.is_entity_valued() {
            return Err(format!("{} does not order a cohort", sort.decl.id).into());
        }
        if sort.decl.cost == Cost::Walk {
            return Err(format!(
                "{} is computed per entity by a tree walk: a page column, not a ranking",
                sort.decl.id
            )
            .into());
        }
        let n = ctx.state.responses.len();
        let (global, intricate) = match filter {
            Some(f) => f.split()?,
            None => (None, None),
        };
        let screened = sort.kind == Kind::Intricate || intricate.is_some();
        let columns = Self::columns(&ctx, &sort, global.iter().chain(intricate.iter()));
        let mut cohort = Self {
            ctx,
            sort,
            filter: None,
            rids: Rids::Identity(n),
            total: n,
            screened,
            columns,
        };
        if global.is_none() && !screened {
            let fixed = match cohort.sort.decl.id {
                metrics::CITATIONS => Some(Rids::Identity(n)),
                _ => ctx.state.orderings.get(&cohort.sort).map(Rids::Fixed),
            };
            if let Some(rids) = fixed {
                cohort.rids = rids;
                return Ok(cohort);
            }
        }
        // Admitted ids in citation order; a screened ranking keeps the top SCREEN_K of them and
        // applies the per-entity clauses to those.
        let admits =
            |b: &Option<Bound>, rid: u32| b.as_ref().is_none_or(|b| b.admits(&ctx, ctx.dm(rid)));
        let mut rids: Vec<u32> = (0..n as u32).filter(|&rid| admits(&global, rid)).collect();
        cohort.total = rids.len();
        if screened {
            rids.truncate(SCREEN_K);
            rids.retain(|&rid| admits(&intricate, rid));
        }
        cohort.rids = if cohort.sort.decl.id == metrics::CITATIONS {
            let values = rids.iter().map(|&rid| cohort.value(rid)).collect();
            Rids::Keyed(rids.into_boxed_slice(), values)
        } else {
            let (rids, values) = order_keyed(rids.into_iter(), |rid| cohort.value(rid));
            Rids::Keyed(rids, values)
        };
        cohort.filter = match (global, intricate) {
            (Some(g), Some(i)) => Some(Bound::And(vec![g, i])),
            (g, i) => g.or(i),
        };
        Ok(cohort)
    }

    // The columns the rows carry: every parameter-free global number of the root, the family of
    // the sort's parameter with the sort's argument, and every parameterized clause of the filter.
    fn columns<'b>(
        ctx: &Ctx,
        sort: &BoundCall,
        filters: impl Iterator<Item = &'b Bound>,
    ) -> Vec<BoundCall> {
        let mut out: Vec<BoundCall> = Vec::new();
        let mut push = |c: BoundCall| {
            if !c.decl.is_entity_valued() && !out.iter().any(|o| o.key == c.key) {
                out.push(c);
            }
        };
        for (decl, kind) in ctx.registry() {
            if decl.param.is_none() && kind == Kind::Global {
                push(BoundCall {
                    decl,
                    arg: Arg::None,
                    kind,
                    key: ctx.canonical_key(decl, Arg::None),
                });
            }
        }
        if let Some(p) = sort.decl.param {
            for (decl, kind) in ctx.registry() {
                if decl.param == Some(p) && decl.cost == Cost::Read {
                    push(BoundCall {
                        decl,
                        arg: sort.arg,
                        kind,
                        key: ctx.canonical_key(decl, sort.arg),
                    });
                }
            }
        }
        for b in filters {
            for c in b.calls() {
                if c.decl.param.is_some() {
                    push(c.clone());
                }
            }
        }
        out
    }

    pub fn len(&self) -> usize {
        self.rids.len()
    }

    pub fn rid_at(&self, pos: usize) -> u32 {
        self.rids.at(pos)
    }

    // The sort metric's value for one response id: the key both the ordering and the rank use.
    fn value(&self, rid: u32) -> f64 {
        self.ctx.num(&self.sort, self.ctx.dm(rid)).unwrap_or(0.0)
    }

    fn value_at(&self, pos: usize) -> f64 {
        match &self.rids {
            Rids::Keyed(_, values) => values[pos],
            rids => self.value(rids.at(pos)),
        }
    }

    // 1-based rank: entities strictly above in the sort value, plus one, so ties share a rank.
    pub fn rank(&self, rid: u32) -> u32 {
        let v = self.value(rid);
        let (mut lo, mut hi) = (0usize, self.len());
        while lo < hi {
            let mid = (lo + hi) / 2;
            if self.value_at(mid).partial_cmp(&v) == Some(Ordering::Greater) {
                lo = mid + 1;
            } else {
                hi = mid;
            }
        }
        lo as u32 + 1
    }

    // None for an entity outside the narrowed cohort or below a screened ranking's cut.
    pub fn rank_of(&self, rid: u32) -> Option<u32> {
        let ranked = match &self.rids {
            Rids::Keyed(rids, _) if self.screened => rids.contains(&rid),
            _ => self
                .filter
                .as_ref()
                .is_none_or(|f| f.admits(&self.ctx, self.ctx.dm(rid))),
        };
        ranked.then(|| self.rank(rid))
    }

    pub fn row(&self, rank: Option<u32>, rid: u32) -> TableRow {
        let dm = self.ctx.dm(rid);
        let values: HashMap<Arc<str>, f64> = self
            .columns
            .iter()
            .filter_map(|c| self.ctx.num(c, dm).map(|v| (c.key.clone(), v)))
            .collect();
        TableRow {
            sr: self.ctx.state.responses[rid as usize].clone(),
            rank,
            values,
        }
    }

    // The metric columns the rows carry, in display order, each keyed by the call's own text.
    pub fn column_keys(&self) -> Vec<Arc<str>> {
        self.columns.iter().map(|c| c.key.clone()).collect()
    }
}

fn unknown(entity: &str, name: &str) -> Reject {
    Reject(format!("no {entity} found for {name:?}"))
}

fn year(v: f64) -> Result<u16, Reject> {
    if v.fract() == 0.0 && (1000.0..=3000.0).contains(&v) {
        Ok(v as u16)
    } else {
        Err(format!("{v} is not a year").into())
    }
}

fn word_name(w: &Word) -> Result<&str, Reject> {
    match w {
        Word::Name(n) => Ok(n.as_str()),
        Word::Num(_) => Err("expected a name".into()),
    }
}
