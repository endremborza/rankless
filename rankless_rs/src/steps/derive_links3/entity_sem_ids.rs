use dmove::{
    ByteFixArrayInterface, CompactEntity, Entity, MarkedAttribute, NamespacedEntity,
    UnsignedNumber, VariableSizeAttribute, ET, MAA,
};

use crate::{
    common::{MainEntity, MainWorkMarker, NameExtensionMarker, NameMarker},
    gen::{
        a1_entity_mapping::{Countries, Works},
        a2_init_atts::{CountryCodes, CountryCodesThree},
    },
    semantic_ids::semantify,
    steps::derive_links3::dec_work_count,
    CiteCountMarker, QuickestBox, ReadFixIter, ReadIter, Stowage,
};

pub(super) fn basic_sem_names(name: &str, _ext: &str) -> Vec<String> {
    vec![semantify(name)]
}

pub(super) fn source_sem_names(name: &str, ext: &str) -> Vec<String> {
    let mut out = Vec::new();
    if !ext.is_empty() {
        out.push(semantify(ext));
    }
    out.push(semantify(name));
    out
}

pub(super) fn institution_sem_names(name: &str, ext: &str) -> Vec<String> {
    let mut out: Vec<String> = ext.split_whitespace().map(semantify).collect();
    const PREF: &str = "University of ";
    const SUFF: &str = " University";
    if name.starts_with(PREF) {
        out.push(semantify(&name[PREF.len()..]));
    }
    if name.ends_with(SUFF) {
        out.push(semantify(&name[..name.len() - SUFF.len()]));
    }
    out.push(semantify(name));
    out
}

pub(super) fn page_filter<E, F, N>(
    stowage: &Stowage,
    extra_filter: F,
    name_fn: N,
) -> (Vec<bool>, Vec<usize>)
where
    E: MainEntity
        + NamespacedEntity
        + MarkedAttribute<CiteCountMarker>
        + MarkedAttribute<NameMarker>
        + MarkedAttribute<MainWorkMarker>
        + MarkedAttribute<NameExtensionMarker>,
    MAA<E, CiteCountMarker>: NamespacedEntity + CompactEntity,
    ET<MAA<E, CiteCountMarker>>: UnsignedNumber + ByteFixArrayInterface,
    MAA<E, NameMarker>: Entity<T = String> + NamespacedEntity + VariableSizeAttribute,
    MAA<E, MainWorkMarker>: Entity<T = Box<[ET<Works>]>> + NamespacedEntity + VariableSizeAttribute,
    MAA<E, NameExtensionMarker>: Entity<T = String> + NamespacedEntity + VariableSizeAttribute,
    F: Fn(usize, usize, usize) -> bool,
    N: Fn(&str, &str) -> Vec<String>,
{
    let cites = stowage.get_marked_interface::<E, CiteCountMarker, QuickestBox>();
    let wcounts: Vec<usize> = stowage
        .get_entity_interface::<MAA<E, MainWorkMarker>, ReadIter>()
        .map(|works| works.len())
        .collect();

    let mut filter = Vec::with_capacity(cites.len());
    let mut name_candidates = Vec::with_capacity(cites.len());

    for (i, (name, ext)) in stowage
        .get_entity_interface::<MAA<E, NameMarker>, ReadIter>()
        .zip(stowage.get_entity_interface::<MAA<E, NameExtensionMarker>, ReadIter>())
        .enumerate()
    {
        let c = cites[i].to_usize();
        let p = wcounts[i];
        let base = !name.trim().is_empty() && p > 1 && c > 2;
        let final_filter_val = base && extra_filter(i, c, p);
        let sem_candidates = if final_filter_val {
            name_fn(&name, &ext)
        } else {
            Vec::new()
        };
        filter.push(final_filter_val);
        name_candidates.push(sem_candidates);
    }

    dec_work_count::<E, _>(stowage, wcounts.iter().copied());
    stowage.write_semantic_id::<E>(&wcounts, &name_candidates);
    (filter, wcounts)
}

pub(super) fn country_page_filter(stowage: &Stowage) -> (Vec<bool>, Vec<usize>) {
    let cc3 = stowage.get_entity_interface::<CountryCodesThree, ReadFixIter>();
    let cc2 = stowage.get_entity_interface::<CountryCodes, ReadFixIter>();
    let wcounts: Vec<usize> = stowage
        .get_entity_interface::<MAA<Countries, MainWorkMarker>, ReadIter>()
        .map(|works: Box<[ET<Works>]>| works.len())
        .collect();

    let mut filter = Vec::new();
    let mut sem_ids: Vec<String> = Vec::new();
    for (e3, e2) in cc3.zip(cc2) {
        let iso = if e3 != [0u8; 3] {
            String::from_utf8(e3.into()).unwrap().to_lowercase()
        } else if e2 != [0u8; 2] {
            String::from_utf8(e2.into()).unwrap().to_lowercase()
        } else {
            String::new()
        };
        filter.push(!iso.is_empty());
        sem_ids.push(iso);
    }

    dec_work_count::<Countries, _>(stowage, wcounts.iter().copied());
    stowage.decsem::<Countries, _>(sem_ids.into_iter());
    (filter, wcounts)
}
