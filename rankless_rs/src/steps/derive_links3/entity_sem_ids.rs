use dmove::{
    ByteFixArrayInterface, CompactEntity, Entity, MarkedAttribute, NamespacedEntity,
    UnsignedNumber, VarSizedAttributeElement, VariableSizeAttribute, ET, MAA,
};

use crate::{
    common::{MainEntity, MainWorkMarker, NameMarker, PageFilterMarker},
    gen::a1_entity_mapping::Works,
    semantic_ids::SemCsvObj,
    CiteCountMarker, QuickestBox, ReadIter, Stowage,
};

pub(super) fn build_filter_and_wcounts<E, F>(stowage: &Stowage, extra: F) -> (Vec<bool>, Vec<usize>)
where
    E: Entity
        + MarkedAttribute<CiteCountMarker>
        + MarkedAttribute<NameMarker>
        + MarkedAttribute<MainWorkMarker>,
    MAA<E, CiteCountMarker>: NamespacedEntity + CompactEntity,
    ET<MAA<E, CiteCountMarker>>: UnsignedNumber + ByteFixArrayInterface,
    MAA<E, NameMarker>: Entity<T = String> + NamespacedEntity + VariableSizeAttribute,
    MAA<E, MainWorkMarker>: Entity + NamespacedEntity + VariableSizeAttribute,
    ET<MAA<E, MainWorkMarker>>: VarSizedAttributeElement + AsRef<[ET<Works>]>,
    F: Fn(usize, usize, usize) -> bool,
{
    let cites = stowage.get_marked_interface::<E, CiteCountMarker, QuickestBox>();
    let wcounts: Vec<usize> = stowage
        .get_entity_interface::<MAA<E, MainWorkMarker>, ReadIter>()
        .map(|works| works.as_ref().len())
        .collect();
    let n = cites.len();
    let mut filter = Vec::with_capacity(n);
    for (i, name) in stowage
        .get_entity_interface::<MAA<E, NameMarker>, ReadIter>()
        .enumerate()
    {
        let c = cites[i].to_usize();
        let p = wcounts[i];
        let base = name.trim().len() > 0 && p > 1 && c > 2;
        filter.push(base && extra(i, c, p));
    }
    stowage.write_semantic_id::<E>(&wcounts, &filter);
    stowage.ditf::<PageFilterMarker, E, _>(filter.clone(), "page-filter");
    (filter, wcounts)
}

impl AddSemId for NamedEntity {
    fn get_names(&self) -> Vec<String> {
        vec![semantify(&self.display_name)]
    }
}

impl AddSemId for FieldLike {
    fn get_names(&self) -> Vec<String> {
        vec![semantify(&self.display_name)]
    }
}

impl AddSemId for Source {
    fn get_names(&self) -> Vec<String> {
        let mut out = read_post_str_arr(&self.alternate_titles);
        if let Some(abb) = &self.abbreviated_title {
            out.push(abb.clone());
        }
        out.push(self.display_name.clone());
        out.sort_by_key(|e| e.len());
        out.iter().map(|s| semantify(s)).collect()
    }
}

impl AddSemId for Institution {
    fn get_names(&self) -> Vec<String> {
        let mut out = read_post_str_arr(&self.display_name_acronyms);
        out.extend(read_post_str_arr(&self.display_name_alternatives).into_iter());
        let base_name = self.display_name.clone();
        out.push(base_name.clone());
        const PREF: &str = "University of ";
        const SUFF: &str = " University";
        if base_name.starts_with(PREF) {
            out.push(base_name[PREF.len()..].to_string())
        }
        if base_name.ends_with(SUFF) {
            out.push(base_name[..base_name.len() - SUFF.len()].to_string())
        }
        out.push(
            format!(
                "{} {}",
                base_name.trim(),
                self.country_code.as_deref().unwrap_or("")
            )
            .to_string(),
        );
        out.sort_by_key(|e| e.len());
        out.iter().map(|s| semantify(s)).collect()
    }
}

fn countr_sids() {
    let cc3 = starc.get_entity_interface::<CountryCodesThree, ReadFixIter>();
    let cc2 = starc.get_entity_interface::<CountryCodes, ReadFixIter>();
    let country_sem_ids = cc3.zip(cc2).enumerate().map(|(i, (e3, e2))| {
        if country_filter[i] {
            String::new()
        } else if e3 != [0; 3] {
            String::from_utf8(e3.into()).unwrap().to_lowercase()
        } else {
            String::from_utf8(e2.into()).unwrap().to_lowercase()
        }
    });
}
