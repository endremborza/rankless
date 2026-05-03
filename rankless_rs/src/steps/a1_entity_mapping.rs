use std::{io, sync::Arc, thread};

use hashbrown::HashSet;
use serde::{de::DeserializeOwned, Deserialize};

use crate::{
    add_parsed_id_traits,
    common::{
        field_id_parse, oa_id_parse_opt, short_string_to_u64, BackendSelector, MarkedBackendLoader,
        ObjIter, ParsedId, Stowage, MAIN_NAME,
    },
    csv_writers::{authors, domains, fields, institutions, sources, subfields, topics, works},
    env_consts::{FINAL_YEAR, START_YEAR},
    oa_structs::{
        post::{Authorship, Institution},
        Geo, IdStruct,
    },
    user_ledger::UserLedger,
    NameMarker, QuickestVBox,
};
use dmove::{
    BigId, Data64MappedEntityBuilder, Entity, EntityImmutableMapperBackend, MappableEntity,
    MarkedAttribute, ET,
};

pub type RawYear = u16;
pub type YBT = [RawYear; N_PERS];
pub const N_PERS: usize = 12;
pub const POSSIBLE_YEAR_FILTERS: YBT = [
    START_YEAR, 1970, 1990, 2000, 2005, 2010, 2015, 2020, 2021, 2022, 2023, 2024,
];

pub struct Years {}
pub struct YearInterface {}
pub struct Qs {}
pub struct QsNames {}

#[derive(Deserialize, Debug)]
pub struct SourceArea {
    id: Option<String>,
    pub area: Option<String>,
}

pub struct ShipIterator {
    raw_iter: ObjIter<Authorship>,
    work_filter: HashSet<BigId>,
}

add_parsed_id_traits!(SourceArea);

impl ShipIterator {
    fn new(stowage: &Stowage) -> Self {
        let raw_iter = stowage.read_csv_objs::<Authorship>(works::C, works::atts::authorships);
        let work_filter = stowage.get_last_filter(works::C).unwrap();
        Self {
            raw_iter,
            work_filter,
        }
    }
}

impl SourceArea {
    pub fn raw_area_id(&self) -> BigId {
        short_string_to_u64(self.area.as_deref().unwrap_or(""))
    }
}

impl YearInterface {
    pub fn reverse(y: ET<Years>) -> RawYear {
        y as RawYear + START_YEAR
    }

    pub fn parse(raw: RawYear) -> ET<Years> {
        (raw - START_YEAR) as ET<Years>
    }

    pub fn iter() -> std::ops::Range<u8> {
        0..((FINAL_YEAR - START_YEAR + 1) as u8)
    }
}

impl Iterator for ShipIterator {
    type Item = Authorship;

    fn next(&mut self) -> Option<Self::Item> {
        while let Some(ship) = self.raw_iter.next() {
            if let Some(wid) = ship.get_parsed_id() {
                if self.work_filter.contains(&wid) {
                    return Some(ship);
                }
            }
        }
        None
    }
}

impl Entity for Years {
    type T = u8;
    const N: usize = (FINAL_YEAR - START_YEAR) as usize;
    const NAME: &'static str = "years";
}

impl Entity for QsNames {
    type T = String;
    const N: usize = 5;
    const NAME: &str = "qs-names";
}

impl Entity for Qs {
    type T = u8;
    const N: usize = 5;
    const NAME: &str = "qs";
}

impl MappableEntity for Qs {
    type KeyType = BigId;
}

impl MappableEntity for QsNames {
    type KeyType = usize;
}

impl MarkedAttribute<NameMarker> for Qs {
    type AttributeEntity = QsNames;
}

impl MarkedBackendLoader<QuickestVBox> for QsNames {
    type BE = <QuickestVBox as BackendSelector<QsNames>>::BE;
    fn load(_stowage: &Stowage) -> Self::BE {
        let mut q_names: Vec<String> = vec!["Uncategorized".to_owned()];
        q_names.extend((1..5).map(|i| format!("Q{}", i)));
        q_names.into()
    }
}

impl MappableEntity for Years {
    type KeyType = RawYear;
}

impl EntityImmutableMapperBackend<Years> for YearInterface {
    fn get_via_immut(&self, k: &RawYear) -> Option<ET<Years>> {
        Some(Self::parse(*k))
    }
}

pub fn main(stowage: Stowage) -> io::Result<()> {
    // Load ledger before Arc-wrapping so we can borrow it across threads.
    let ledger = UserLedger::load(&stowage)?;
    let author_aliases = Arc::new(ledger.author_aliases.clone());
    let work_aliases = Arc::new(ledger.work_aliases.clone());

    let mut threads = Vec::new();
    let starc = Arc::new(stowage);

    for sw in vec![fields::C, subfields::C, domains::C] {
        let sc = starc.clone();
        threads.push(thread::spawn(move || {
            ids_from_atts::<IdStruct, _>(&sc, sw, sw, |e| Some(field_id_parse(&e.id.unwrap())));
        }));
    }

    // Works: skip drop-side alias oa_ids so they get no dm_id.
    let work_filter_thread = {
        let sc = starc.clone();
        let wa = work_aliases.clone();
        thread::spawn(move || {
            ids_from_atts::<IdStruct, _>(&sc, works::C, works::C, |e| {
                e.get_parsed_id().filter(|id| !wa.contains_key(id))
            })
        })
    };
    for en in vec![institutions::C, sources::C, topics::C] {
        let sc = starc.clone();
        threads.push(thread::spawn(move || {
            ids_from_atts::<IdStruct, _>(&sc, en, en, |e| e.get_parsed_id());
        }));
    }

    let author_filter = starc.get_last_filter(authors::C).unwrap();
    {
        let sc = starc.clone();
        let filter = author_filter.clone();
        let aa = author_aliases.clone();
        threads.push(thread::spawn(move || {
            let mut selected_authors = Vec::new();
            let a_iter = sc
                .read_csv_objs::<IdStruct>(authors::C, MAIN_NAME)
                .filter_map(|e| {
                    if let Some(pid) = e.get_parsed_id() {
                        if aa.contains_key(&pid) {
                            // Drop-side alias: no dm_id in any space.
                            return None;
                        }
                        if filter.contains(&pid) {
                            selected_authors.push(pid);
                            return None;
                        }
                        Some(pid)
                    } else {
                        None
                    }
                });
            sc.add_iter_owned::<Data64MappedEntityBuilder, _, _>(a_iter, Some("discarded-authors"));
            sc.add_iter_owned::<Data64MappedEntityBuilder, _, _>(
                selected_authors.into_iter(),
                Some(authors::C),
            );
        }));
    }

    {
        let sc = starc.clone();
        threads.push(thread::spawn(move || {
            ids_from_atts::<SourceArea, _>(&sc, "area-fields", sources::C, |e| {
                Some(e.raw_area_id())
            });
        }));
    }
    {
        let sc = starc.clone();
        threads.push(thread::spawn(move || {
            ids_from_atts::<Institution, _>(&sc, "countries", institutions::C, |e| {
                Some(short_string_to_u64(e.country_code.as_deref().unwrap_or("")))
            });
        }));
    }
    {
        let sc = starc.clone();
        threads.push(thread::spawn(move || {
            entities_from_iter(
                &sc,
                "cities",
                sc.read_csv_objs::<Geo>(institutions::C, institutions::atts::geo)
                    .map(|e| short_string_to_u64(e.city.as_deref().unwrap_or(""))),
                &None,
            );
        }));
    }

    let mut filt_ship_n = 0;
    let mut disc_ship_n = 0;
    for ship in iter_authorships(&starc) {
        if let Some(raw_a_oaid) = ship.author_id {
            if let Some(aid) = oa_id_parse_opt(&raw_a_oaid) {
                // Aliases redirect to keep; for counting purposes use effective id.
                let effective = author_aliases.get(&aid).copied().unwrap_or(aid);
                if author_filter.contains(&effective) {
                    filt_ship_n += 1;
                } else {
                    disc_ship_n += 1;
                }
            }
        }
    }
    threads.into_iter().for_each(|h| h.join().unwrap());
    starc
        .mu_bu()
        .add_scaled_entity("authorships-filtered-author", filt_ship_n, true);
    starc
        .mu_bu()
        .add_scaled_entity("authorships-discarded-author", disc_ship_n, true);
    starc.write_code()?;

    // Manifest: record which merge events were applied vs skipped.
    let work_filter = work_filter_thread.join().unwrap().unwrap();
    ledger.write_a1_manifest(&starc, &author_filter, &work_filter)?;

    Ok(())
}

pub fn iter_authorships(stowage: &Stowage) -> ShipIterator {
    ShipIterator::new(stowage)
}

fn ids_from_atts<T, F>(
    stowage: &Stowage,
    out_name: &str,
    parent_entity: &str,
    closure: F,
) -> Option<HashSet<BigId>>
where
    T: DeserializeOwned,
    F: Fn(T) -> Option<BigId>,
{
    let last_filter = stowage.get_last_filter(out_name);
    entities_from_iter(
        stowage,
        out_name,
        stowage
            .read_csv_objs::<T>(parent_entity, MAIN_NAME)
            .filter_map(closure),
        &last_filter,
    );
    last_filter
}

fn entities_from_iter<I>(stowage: &Stowage, name: &str, iter: I, filter: &Option<HashSet<BigId>>)
where
    I: Iterator<Item = BigId>,
{
    match filter {
        None => {
            println!("{name} no filter");
            stowage.add_iter_owned::<Data64MappedEntityBuilder, _, _>(iter, Some(name));
        }
        Some(fs) => {
            println!("{name} filter of {:?}", fs.len());
            stowage.add_iter_owned::<Data64MappedEntityBuilder, _, _>(
                iter.filter(|e| fs.contains(e)),
                Some(name),
            );
        }
    };
}
