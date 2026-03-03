use dmove::{MappableEntity, NamespacedEntity, MarkedAttribute, VariableSizeAttribute, Entity};

pub struct TopicsHits { }

pub struct AuthorsHits { }

pub struct AuthorCitingHitsDirect { }

pub struct CountriesHits { }

pub struct InstitutionsHits { }

pub struct CountriesWorkCount { }

pub struct SubfieldsHits { }

pub struct SourcesHits { }

pub struct AuthorCitingHitsOnce { }

impl Entity for CountriesWorkCount { type T = u32; const N: usize = 233; const NAME: & str = "countries-work-count"; }

impl MappableEntity for CountriesWorkCount { type KeyType = usize; }

impl NamespacedEntity for CountriesWorkCount { const NS: & str = "derive_links4"; }

impl MarkedAttribute<crate::common::WorkCountMarker> for crate::gen::a1_entity_mapping::Countries { type AttributeEntity = CountriesWorkCount; }

impl Entity for CountriesHits { type T = Box<[u32]>; const N: usize = 233; const NAME: & str = "countries-hits"; }

impl MappableEntity for CountriesHits { type KeyType = usize; }

impl VariableSizeAttribute for CountriesHits { type SizeType = u32; type LocType = u32; }

impl NamespacedEntity for CountriesHits { const NS: & str = "derive_links4"; }

impl MarkedAttribute<crate::common::HitWorkMarker> for crate::gen::a1_entity_mapping::Countries { type AttributeEntity = CountriesHits; }

impl Entity for InstitutionsHits { type T = Box<[u32]>; const N: usize = 33245; const NAME: & str = "institutions-hits"; }

impl MappableEntity for InstitutionsHits { type KeyType = usize; }

impl VariableSizeAttribute for InstitutionsHits { type SizeType = u16; type LocType = u32; }

impl NamespacedEntity for InstitutionsHits { const NS: & str = "derive_links4"; }

impl MarkedAttribute<crate::common::HitWorkMarker> for crate::gen::a1_entity_mapping::Institutions { type AttributeEntity = InstitutionsHits; }

impl Entity for SubfieldsHits { type T = Box<[u32]>; const N: usize = 254; const NAME: & str = "subfields-hits"; }

impl MappableEntity for SubfieldsHits { type KeyType = usize; }

impl VariableSizeAttribute for SubfieldsHits { type SizeType = u16; type LocType = u32; }

impl NamespacedEntity for SubfieldsHits { const NS: & str = "derive_links4"; }

impl MarkedAttribute<crate::common::HitWorkMarker> for crate::gen::a1_entity_mapping::Subfields { type AttributeEntity = SubfieldsHits; }

impl Entity for SourcesHits { type T = Box<[u32]>; const N: usize = 41067; const NAME: & str = "sources-hits"; }

impl MappableEntity for SourcesHits { type KeyType = usize; }

impl VariableSizeAttribute for SourcesHits { type SizeType = u32; type LocType = u32; }

impl NamespacedEntity for SourcesHits { const NS: & str = "derive_links4"; }

impl MarkedAttribute<crate::common::HitWorkMarker> for crate::gen::a1_entity_mapping::Sources { type AttributeEntity = SourcesHits; }

impl Entity for TopicsHits { type T = Box<[u32]>; const N: usize = 4518; const NAME: & str = "topics-hits"; }

impl MappableEntity for TopicsHits { type KeyType = usize; }

impl VariableSizeAttribute for TopicsHits { type SizeType = u16; type LocType = u32; }

impl NamespacedEntity for TopicsHits { const NS: & str = "derive_links4"; }

impl MarkedAttribute<crate::common::HitWorkMarker> for crate::gen::a1_entity_mapping::Topics { type AttributeEntity = TopicsHits; }

impl Entity for AuthorsHits { type T = Box<[u32]>; const N: usize = 4175973; const NAME: & str = "authors-hits"; }

impl MappableEntity for AuthorsHits { type KeyType = usize; }

impl VariableSizeAttribute for AuthorsHits { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for AuthorsHits { const NS: & str = "derive_links4"; }

impl MarkedAttribute<crate::common::HitWorkMarker> for crate::gen::a1_entity_mapping::Authors { type AttributeEntity = AuthorsHits; }

impl Entity for AuthorCitingHitsDirect { type T = Box<[u32]>; const N: usize = 4175973; const NAME: & str = "author-citing-hits-direct"; }

impl MappableEntity for AuthorCitingHitsDirect { type KeyType = usize; }

impl VariableSizeAttribute for AuthorCitingHitsDirect { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for AuthorCitingHitsDirect { const NS: & str = "derive_links4"; }

impl Entity for AuthorCitingHitsOnce { type T = Box<[u32]>; const N: usize = 4175973; const NAME: & str = "author-citing-hits-once"; }

impl MappableEntity for AuthorCitingHitsOnce { type KeyType = usize; }

impl VariableSizeAttribute for AuthorCitingHitsOnce { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for AuthorCitingHitsOnce { const NS: & str = "derive_links4"; }