use dmove::{MarkedAttribute, Entity, Link, VariableSizeAttribute, MappableEntity, NamespacedEntity};

pub struct InstitutionsWorkCount { }

pub struct AuthorsWorkCount { }

pub struct Coauthors { }

pub struct TopicsWorkCount { }

pub struct HitPapersCiteCounts { }

pub struct SubfieldsWorkCount { }

pub struct SourcesWorkCount { }

pub struct HitPapers { }

pub struct HitPapersDois { }

pub struct HitPapersWids { }

pub struct HitPapersNames { }

pub struct CountryWorks { }

impl Entity for InstitutionsWorkCount { type T = u32; const N: usize = 30283; const NAME: & str = "institutions-work-count"; }

impl MappableEntity for InstitutionsWorkCount { type KeyType = usize; }

impl NamespacedEntity for InstitutionsWorkCount { const NS: & str = "derive_links3"; }

impl MarkedAttribute<crate::common::WorkCountMarker> for crate::gen::a1_entity_mapping::Institutions { type AttributeEntity = InstitutionsWorkCount; }

impl Entity for SubfieldsWorkCount { type T = u32; const N: usize = 254; const NAME: & str = "subfields-work-count"; }

impl MappableEntity for SubfieldsWorkCount { type KeyType = usize; }

impl NamespacedEntity for SubfieldsWorkCount { const NS: & str = "derive_links3"; }

impl MarkedAttribute<crate::common::WorkCountMarker> for crate::gen::a1_entity_mapping::Subfields { type AttributeEntity = SubfieldsWorkCount; }

impl Entity for TopicsWorkCount { type T = u32; const N: usize = 4518; const NAME: & str = "topics-work-count"; }

impl MappableEntity for TopicsWorkCount { type KeyType = usize; }

impl NamespacedEntity for TopicsWorkCount { const NS: & str = "derive_links3"; }

impl MarkedAttribute<crate::common::WorkCountMarker> for crate::gen::a1_entity_mapping::Topics { type AttributeEntity = TopicsWorkCount; }

impl Entity for SourcesWorkCount { type T = u32; const N: usize = 40060; const NAME: & str = "sources-work-count"; }

impl MappableEntity for SourcesWorkCount { type KeyType = usize; }

impl NamespacedEntity for SourcesWorkCount { const NS: & str = "derive_links3"; }

impl MarkedAttribute<crate::common::WorkCountMarker> for crate::gen::a1_entity_mapping::Sources { type AttributeEntity = SourcesWorkCount; }

impl Entity for AuthorsWorkCount { type T = u16; const N: usize = 4037517; const NAME: & str = "authors-work-count"; }

impl MappableEntity for AuthorsWorkCount { type KeyType = usize; }

impl NamespacedEntity for AuthorsWorkCount { const NS: & str = "derive_links3"; }

impl MarkedAttribute<crate::common::WorkCountMarker> for crate::gen::a1_entity_mapping::Authors { type AttributeEntity = AuthorsWorkCount; }

impl Entity for CountryWorks { type T = Box<[u32]>; const N: usize = 230; const NAME: & str = "country-works"; }

impl MappableEntity for CountryWorks { type KeyType = usize; }

impl VariableSizeAttribute for CountryWorks { type SizeType = u32; type LocType = u32; }

impl NamespacedEntity for CountryWorks { const NS: & str = "derive_links3"; }

impl Link for CountryWorks { type Source = crate::gen::a1_entity_mapping::Countries; type Target = crate::gen::a1_entity_mapping::Works; }

impl MarkedAttribute<crate::common::MainWorkMarker> for crate::gen::a1_entity_mapping::Countries { type AttributeEntity = CountryWorks; }

impl Entity for HitPapers { type T = u32; const N: usize = 77409; const NAME: & str = "hit-papers"; }

impl MappableEntity for HitPapers { type KeyType = u64; }

impl NamespacedEntity for HitPapers { const NS: & str = "derive_links3"; }

impl Entity for HitPapersNames { type T = String; const N: usize = 77409; const NAME: & str = "hit-papers-names"; }

impl MappableEntity for HitPapersNames { type KeyType = usize; }

impl VariableSizeAttribute for HitPapersNames { type SizeType = u16; type LocType = u32; }

impl NamespacedEntity for HitPapersNames { const NS: & str = "derive_links3"; }

impl Entity for HitPapersDois { type T = String; const N: usize = 77409; const NAME: & str = "hit-papers-dois"; }

impl MappableEntity for HitPapersDois { type KeyType = usize; }

impl VariableSizeAttribute for HitPapersDois { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for HitPapersDois { const NS: & str = "derive_links3"; }

impl Entity for HitPapersWids { type T = Box<[u32]>; const N: usize = 77409; const NAME: & str = "hit-papers-wids"; }

impl MappableEntity for HitPapersWids { type KeyType = usize; }

impl VariableSizeAttribute for HitPapersWids { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for HitPapersWids { const NS: & str = "derive_links3"; }

impl Entity for Coauthors { type T = Box<[(u32, u8)]>; const N: usize = 4037517; const NAME: & str = "coauthors"; }

impl MappableEntity for Coauthors { type KeyType = usize; }

impl VariableSizeAttribute for Coauthors { type SizeType = u16; type LocType = u32; }

impl NamespacedEntity for Coauthors { const NS: & str = "derive_links3"; }

impl Entity for HitPapersCiteCounts { type T = u32; const N: usize = 77409; const NAME: & str = "hit-papers-cite-counts"; }

impl MappableEntity for HitPapersCiteCounts { type KeyType = usize; }

impl NamespacedEntity for HitPapersCiteCounts { const NS: & str = "derive_links3"; }