use std::io;

use crate::{
    common::{
        init_empty_slice, BackendSelector, BeS, MainWorkMarker, MarkedBackendLoader, QuickAttPair,
        QuickestBox, QuickestVBox, ReadIter, Stowage,
    },
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Works},
        a2_init_atts::{
            AuthorshipFilteredAuthor, DiscardedAuthorshipInstitutions,
            FilteredAuthorshipInstitutions, InstCountries, TopicSubfields, WorkAnyAuthorships,
            WorkReferences, WorkSources, WorkTopics, WorkYears,
        },
    },
    ReadFixIter,
};

use dmove::{
    reverse_prefixed_n, BackendLoading, ByteArrayInterface, ByteFixArrayInterface, CompactEntity,
    Entity, EntityImmutableRefMapperBackend, Link, MappableEntity, NamespacedEntity,
    UnsignedNumber, VarAttBuilder, VarSizedAttributeElement, VariableSizeAttribute, VattArrPair,
    ET,
};

use super::a1_entity_mapping::{YearInterface, N_PERS, POSSIBLE_YEAR_FILTERS};

pub struct WorkPeriods {}
pub struct CountryInsts {}

impl WorkPeriods {
    pub fn from_year(year: u16) -> ET<Self> {
        for i in (0..N_PERS).rev() {
            if year >= POSSIBLE_YEAR_FILTERS[i] {
                return i as u8;
            }
        }
        0
    }
}

impl MarkedBackendLoader<QuickestBox> for WorkPeriods {
    type BE = BeS<QuickestBox, Self>;
    fn load(stowage: &Stowage) -> Self::BE {
        let wys = stowage.get_entity_interface::<WorkYears, ReadFixIter>();
        wys.map(|y_id| {
            let y = YearInterface::reverse(y_id);
            Self::from_year(y)
        })
        .collect()
    }
}

impl MarkedBackendLoader<QuickestVBox> for CountryInsts {
    type BE = BeS<QuickestVBox, Self>;
    fn load(stowage: &Stowage) -> Self::BE {
        let inst_c = stowage.get_entity_interface::<InstCountries, ReadFixIter>();
        let mut c_insts = init_empty_slice::<Countries, Vec<ET<Institutions>>>();
        inst_c.enumerate().for_each(|(iid, cid)| {
            c_insts[cid.to_usize()].push(<Institutions as Entity>::T::from_usize(iid));
        });
        c_insts
            .into_vec()
            .into_iter()
            .map(|e| e.into_boxed_slice())
            .collect()
    }
}

impl MarkedBackendLoader<QuickAttPair> for CountryInsts {
    type BE = VattArrPair<Self>;
    fn load(stowage: &Stowage) -> Self::BE {
        let boxes = <Self as MarkedBackendLoader<QuickestVBox>>::load(stowage);
        Self::BE::from_boxes(boxes)
    }
}

impl Entity for WorkPeriods {
    type T = u8;
    const N: usize = Works::N;
    const NAME: &'static str = "work-periods";
}

impl Entity for CountryInsts {
    type T = Box<[ET<Institutions>]>;
    const N: usize = Countries::N;
    const NAME: &'static str = "country-insts";
}

impl MappableEntity for WorkPeriods {
    type KeyType = usize;
}

impl MappableEntity for CountryInsts {
    type KeyType = usize;
}

impl VariableSizeAttribute for CountryInsts {
    type SizeType = u32;
    type LocType = u32;
}

pub fn invert_read_multi_link_to_work<L>(stowage: &Stowage, name: &str)
where
    L: Entity<T = Box<[ET<L::Target>]>>
        + Link<Source = Works>
        + NamespacedEntity
        + CompactEntity
        + VariableSizeAttribute,
    ET<L::Source>: UnsignedNumber,
    ET<L::Target>: UnsignedNumber,
{
    let interface = stowage.get_entity_interface::<L, ReadIter>();
    invert_multi_link::<L, _>(stowage, interface, name, true);
    stowage.declare::<L::Target, MainWorkMarker>(name);
}

pub fn invert_multi_link<L, LIF>(stowage: &Stowage, interface: LIF, name: &str, ignore_zero: bool)
where
    L: Entity<T = Box<[ET<L::Target>]>> + Link,
    ET<L::Source>: UnsignedNumber,
    ET<L::Target>: UnsignedNumber,
    LIF: Iterator<Item = L::T>,
{
    let inverted = get_inverted_multi::<L, LIF>(interface, ignore_zero);
    stowage.add_barr::<VarAttBuilder, _>(inverted, name);
    stowage.declare_link::<L::Target, L::Source>(name);
}

pub fn get_inverted_multi<L, LIF>(interface: LIF, ignore_zero: bool) -> Box<[Box<[ET<L::Source>]>]>
where
    L: Entity<T = Box<[ET<L::Target>]>> + Link,
    ET<L::Source>: UnsignedNumber,
    ET<L::Target>: UnsignedNumber,
    LIF: Iterator<Item = L::T>,
{
    let mut inverted = init_empty_slice::<L::Target, Vec<<L::Source as Entity>::T>>();
    for (source_id, target_slice) in interface.enumerate() {
        for target_id in target_slice.iter() {
            let tidu = target_id.to_usize();
            if ignore_zero & (tidu == 0) {
                continue;
            }
            inverted[tidu].push(<L::Source as Entity>::T::from_usize(source_id))
        }
    }
    inverted
        .into_vec()
        .into_iter()
        .map(|e| e.into_boxed_slice())
        .collect()
}

pub fn collapse_links<Link1, Link2>(stowage: &mut Stowage, name: &str)
where
    Link1: Link + NamespacedEntity + VariableSizeAttribute,
    Link2: Link + Entity<T = ET<Link2::Target>> + NamespacedEntity + CompactEntity,
    ET<Link1>: ByteArrayInterface + VarSizedAttributeElement,
    ET<Link1::Target>: UnsignedNumber,
    ET<Link2::Target>: UnsignedNumber,
    BeS<ReadIter, Link1>: Iterator<Item = Box<[ET<Link1::Target>]>>,
{
    let cloj = |ends: &mut Vec<Link2::T>, fw_target: &Link2::T| {
        if !ends.contains(fw_target) {
            ends.push(*fw_target);
        }
    };
    collapse_links_meta::<Link1, Link2, QuickestBox, _>(stowage, name, cloj)
}

pub fn collapse_links_mtarget<Link1, Link2>(stowage: &mut Stowage, name: &str)
where
    Link1: Link + NamespacedEntity + VariableSizeAttribute,
    Link2: Entity<T = Box<[ET<Link2::Target>]>>
        + NamespacedEntity
        + CompactEntity
        + VariableSizeAttribute
        + Link,
    ET<Link1>: ByteArrayInterface + VarSizedAttributeElement,
    ET<Link1::Target>: UnsignedNumber,
    ET<Link2::Target>: UnsignedNumber,
    BeS<ReadIter, Link1>: Iterator<Item = Box<[ET<Link1::Target>]>>,
{
    let cloj = |ends: &mut Vec<<Link2::Target as Entity>::T>, fw_targets: &Link2::T| {
        for fw_target in fw_targets {
            if !ends.contains(fw_target) {
                ends.push(*fw_target);
            }
        }
    };
    collapse_links_meta::<Link1, Link2, QuickestVBox, _>(stowage, name, cloj)
}

pub fn main(mut stowage: Stowage) -> io::Result<()> {
    invert_read_multi_link_to_work::<WorkReferences>(&mut stowage, "works-citing");
    invert_read_multi_link_to_work::<WorkTopics>(&mut stowage, "topic-works");
    invert_read_multi_link_to_work::<WorkSources>(&mut stowage, "source-works");

    collapse_links::<WorkTopics, TopicSubfields>(&mut stowage, "work-subfields");

    let ship_fats = stowage.get_entity_interface::<AuthorshipFilteredAuthor, QuickestBox>();
    let fship_is = stowage.get_entity_interface::<FilteredAuthorshipInstitutions, QuickestVBox>();
    let dship_is = stowage.get_entity_interface::<DiscardedAuthorshipInstitutions, QuickestVBox>();

    let mut w_fauthors = init_empty_slice::<Works, Vec<ET<Authors>>>();
    let mut w_allinsts = init_empty_slice::<Works, Vec<ET<Institutions>>>();

    for (wid, w_any_ships) in stowage
        .get_entity_interface::<WorkAnyAuthorships, ReadIter>()
        .enumerate()
    {
        for anyship_id in w_any_ships.iter() {
            let (is_fileterd, ship_id) = reverse_prefixed_n(anyship_id.to_usize());
            let iis = if is_fileterd {
                let aid = ship_fats[ship_id];
                if !w_fauthors[wid].contains(&aid) {
                    w_fauthors[wid].push(aid);
                }

                &fship_is.0[ship_id]
            } else {
                &dship_is.0[ship_id]
            };
            for iid in iis {
                if !w_allinsts[wid].contains(iid) {
                    w_allinsts[wid].push(*iid);
                }
            }
        }
    }

    let wfa_name = "work-filtered-authors";
    let w2i_name = "work-institutions";
    stowage.add_barr_of_vecs(w_fauthors, wfa_name);
    stowage.add_barr_of_vecs(w_allinsts, w2i_name);
    stowage.declare_link::<Works, Authors>(wfa_name);
    stowage.declare_link::<Works, Institutions>(w2i_name);
    stowage.write_code()?;
    Ok(())
}

fn collapse_links_meta<Link1, Link2, IfMarker, F>(stowage: &mut Stowage, name: &str, fun: F)
where
    Link1: Link + NamespacedEntity + VariableSizeAttribute,
    Link2: Link + NamespacedEntity + CompactEntity,
    IfMarker: BackendSelector<Link2>,
    F: Fn(&mut Vec<ET<Link2::Target>>, &<Link2 as Entity>::T),
    Link1::T: ByteArrayInterface + VarSizedAttributeElement,
    ET<Link1::Target>: UnsignedNumber,
    ET<Link2::Target>: ByteFixArrayInterface,
    BeS<ReadIter, Link1>: Iterator<Item = Box<[ET<Link1::Target>]>>,
    <IfMarker as BackendSelector<Link2>>::BE:
        EntityImmutableRefMapperBackend<Link2> + BackendLoading<Link2>,
{
    let mut collapsed = Vec::new();
    let l1_interface = stowage.get_entity_interface::<Link1, ReadIter>();
    let l2_interface = stowage.get_entity_interface::<Link2, IfMarker>();
    for mid_targets in l1_interface {
        let mut ends = Vec::new();
        for mt in mid_targets {
            let fw_target = l2_interface.get_ref_via_immut(&mt.to_usize()).unwrap();
            fun(&mut ends, fw_target);
        }
        collapsed.push(ends.into_boxed_slice());
    }
    stowage.add_iter_owned::<VarAttBuilder, _, _>(collapsed.into_iter(), Some(name));
    stowage.declare_link::<Link1::Source, Link2::Target>(name);
}
