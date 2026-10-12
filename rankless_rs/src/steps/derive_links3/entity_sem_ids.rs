use dmove::{
    BigId, ByteFixArrayInterface, CompactEntity, Entity, MarkedAttribute, NamespacedEntity,
    UnsignedNumber, VariableSizeAttribute, ET, MAA,
};

use crate::{
    common::{MainEntity, MainWorkMarker, NameExtensionMarker, NameMarker, EXT_SEP},
    gen::{
        a1_entity_mapping::{Countries, Works},
        a2_init_atts::{CountryCodes, CountryCodesThree},
    },
    semantic_ids::{semantify, SemCandidates},
    steps::derive_links3::dec_work_count,
    CiteCountMarker, QuickestBox, QuickestNumbered, ReadFixIter, ReadIter, Stowage,
};

// Alternate titles mix acronyms with former and translated titles; a one-word title this short
// is an acronym, a longer one ("Yearbook", "Session") usually a former or generic title.
const MAX_SOURCE_ACRONYM_LEN: usize = 5;
// `etype,openalex_id,semantic_id,why`: an entity's slug pinned over the candidate rule.
const SEM_ID_PINS: &str = include_str!("../../../static/semantic-id-pins.csv");

pub(super) fn basic_sem_names(name: &str, _ext: &str) -> SemCandidates {
    SemCandidates::name_only(semantify(name))
}

pub(super) fn source_sem_names(name: &str, ext: &str) -> SemCandidates {
    alternate_candidates(name, ext, |s| {
        is_acronym(s) && s.len() <= MAX_SOURCE_ACRONYM_LEN
    })
}

pub(super) fn institution_sem_names(name: &str, ext: &str) -> SemCandidates {
    let mut c = alternate_candidates(name, ext, is_acronym);
    let unprefixed = name.strip_prefix("The ").unwrap_or(name);
    c.preferred
        .extend(unprefixed.strip_prefix("University of ").map(semantify));
    c.preferred
        .extend(name.strip_suffix(" University").map(semantify));
    c
}

/// Latin alternates `acronym` accepts are preferred. A name in another script transliterates into
/// a slug few readers recognise, so its other Latin alternates are preferred after them; every
/// other alternate is a fallback.
fn alternate_candidates(name: &str, ext: &str, acronym: impl Fn(&str) -> bool) -> SemCandidates {
    let latin_name = is_latin(name);
    let (mut preferred, mut latin, mut fallbacks) = (Vec::new(), Vec::new(), Vec::new());
    for raw in ext.split(EXT_SEP) {
        let slug = semantify(raw);
        if slug.is_empty() {
            continue;
        }
        let candidates = match (is_latin(raw), acronym(&slug)) {
            (true, true) => &mut preferred,
            (true, false) if !latin_name => &mut latin,
            _ => &mut fallbacks,
        };
        candidates.push(slug);
    }
    preferred.append(&mut latin);
    SemCandidates {
        preferred,
        name: semantify(name),
        fallbacks,
    }
}

fn is_acronym(slug: &str) -> bool {
    slug.len() > 1 && !slug.contains('-')
}

// ASCII and the accented Latin letters, which keep their reading once deunicode strips the marks.
fn is_latin(s: &str) -> bool {
    s.chars()
        .filter(|c| c.is_alphabetic())
        .all(|c| c.is_ascii() || matches!(c, '\u{c0}'..='\u{24f}' | '\u{1e00}'..='\u{1eff}'))
}

fn pinned_sem_ids<E>(stowage: &Stowage) -> Vec<(usize, String)>
where
    E: MainEntity + NamespacedEntity,
{
    let pins: Vec<(BigId, &str)> = SEM_ID_PINS
        .lines()
        .skip(1)
        .filter_map(|line| {
            let mut fields = line.splitn(4, ',');
            let (Some(etype), Some(oa_id), Some(sem_id)) =
                (fields.next(), fields.next(), fields.next())
            else {
                panic!("malformed semantic id pin: {line}");
            };
            let oa_id = oa_id[1..]
                .parse()
                .unwrap_or_else(|_| panic!("malformed OpenAlex id: {oa_id}"));
            (etype == E::NAME).then_some((oa_id, sem_id))
        })
        .collect();
    if pins.is_empty() {
        return Vec::new();
    }
    let ids = stowage.get_entity_interface::<E, QuickestNumbered>();
    pins.into_iter()
        .filter_map(|(oa_id, sem_id)| Some((ids.0.get(&oa_id)?.to_usize(), sem_id.to_string())))
        .collect()
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
    N: Fn(&str, &str) -> SemCandidates,
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
        let base = !name.trim().is_empty() && p > 1 && c > 1;
        let final_filter_val = base && extra_filter(i, c, p);
        filter.push(final_filter_val);
        name_candidates.push(final_filter_val.then(|| name_fn(&name, &ext)));
    }

    dec_work_count::<E, _>(stowage, wcounts.iter().copied());
    stowage.write_semantic_id::<E>(&wcounts, &name_candidates, &pinned_sem_ids::<E>(stowage));
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

#[cfg(test)]
mod tests {
    use super::*;

    fn exts(entries: &[&str]) -> String {
        entries.join(EXT_SEP)
    }

    #[test]
    fn a_source_prefers_only_short_one_word_alternates() {
        let c = source_sem_names(
            "Physical Review Letters",
            &exts(&["prl", "physical review letters online", "yearbook", "c"]),
        );
        assert_eq!(c.preferred, ["prl"]);
        assert_eq!(c.name, "physical-review-letters");
        assert_eq!(
            c.fallbacks,
            ["physical-review-letters-online", "yearbook", "c"]
        );
    }

    #[test]
    fn an_institution_prefers_its_acronyms_then_its_short_name() {
        let c = institution_sem_names(
            "University of Toronto",
            &exts(&["uoft", "university toronto"]),
        );
        assert_eq!(c.preferred, ["uoft", "toronto"]);
        assert_eq!(c.name, "university-of-toronto");
        assert_eq!(c.fallbacks, ["university-toronto"]);
        let c = institution_sem_names("The University of Melbourne", "");
        assert_eq!(c.preferred, ["melbourne"]);
    }

    #[test]
    fn latin_alternates_outrank_a_name_in_another_script() {
        let c = institution_sem_names("삼성", &exts(&["삼성전자", "samsung (south korea)", "sec"]));
        assert_eq!(c.preferred, ["sec", "samsung-south-korea"]);
        assert_eq!(c.fallbacks, [semantify("삼성전자")]);
        let c = source_sem_names("地震学报", &exts(&["earthquake science"]));
        assert_eq!(c.preferred, ["earthquake-science"]);
        assert_eq!(c.name, "di-zhen-xue-bao");
    }
}
