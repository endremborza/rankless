use dmove::{MarkedAttribute, Entity, Link, VariableSizeAttribute, MappableEntity, NamespacedEntity};

pub struct AuthorOrcids { }

pub struct WorkSources { }

pub struct DomainsNames { }

pub struct InstLocs { }

pub struct FilteredAuthorshipInstitutions { }

pub struct AuthorsNames { }

pub struct TopicsNames { }

pub struct InstCountries { }

pub struct TopicSubfields { }

pub struct WorkReferences { }

pub struct WorkAnyAuthorships { }

pub struct WorkBiblios { }

pub struct InstitutionsNames { }

pub struct AuthorRawCites { }

pub struct InstitutionsNameExts { }

pub struct CountryCodesThree { }

pub struct SubfieldsWikipedia { }

pub struct FieldAncestors { }

pub struct InstCities { }

pub struct InstRors { }

pub struct TopicsWikipedia { }

pub struct WorkDois { }

pub struct WorkTopics { }

pub struct SubfieldAncestors { }

pub struct CountriesNames { }

pub struct SourcesNameExts { }

pub struct AuthorshipFilteredAuthor { }

pub struct AuthorshipDiscardedAuthor { }

pub struct DiscardedAuthorshipInstitutions { }

pub struct AuthorWikiSlugs { }

pub struct DiscardedAuthorsNames { }

pub struct CitiesNames { }

pub struct AuthorRawWorkCounts { }

pub struct FieldsNames { }

pub struct CountriesNameExts { }

pub struct WorkYears { }

pub struct WorksNames { }

pub struct SubfieldsNameExts { }

pub struct AuthorsNameExts { }

pub struct CountryCodes { }

pub struct SubfieldsNames { }

pub struct SourceYearQs { }

pub struct SourcesNames { }

pub struct SourceAreaFields { }

impl Entity for AuthorshipFilteredAuthor { type T = u32; const N: usize = 191078698; const NAME: & str = "authorship-filtered-author"; }

impl MappableEntity for AuthorshipFilteredAuthor { type KeyType = usize; }

impl NamespacedEntity for AuthorshipFilteredAuthor { const NS: & str = "a2_init_atts"; }

impl Entity for AuthorshipDiscardedAuthor { type T = u32; const N: usize = 96690822; const NAME: & str = "authorship-discarded-author"; }

impl MappableEntity for AuthorshipDiscardedAuthor { type KeyType = usize; }

impl NamespacedEntity for AuthorshipDiscardedAuthor { const NS: & str = "a2_init_atts"; }

impl Entity for FilteredAuthorshipInstitutions { type T = Box<[u16]>; const N: usize = 191078698; const NAME: & str = "filtered-authorship-institutions"; }

impl MappableEntity for FilteredAuthorshipInstitutions { type KeyType = usize; }

impl VariableSizeAttribute for FilteredAuthorshipInstitutions { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for FilteredAuthorshipInstitutions { const NS: & str = "a2_init_atts"; }

impl Entity for DiscardedAuthorshipInstitutions { type T = Box<[u16]>; const N: usize = 96690822; const NAME: & str = "discarded-authorship-institutions"; }

impl MappableEntity for DiscardedAuthorshipInstitutions { type KeyType = usize; }

impl VariableSizeAttribute for DiscardedAuthorshipInstitutions { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for DiscardedAuthorshipInstitutions { const NS: & str = "a2_init_atts"; }

impl Entity for WorkAnyAuthorships { type T = Box<[u32]>; const N: usize = 75090099; const NAME: & str = "work-any-authorships"; }

impl MappableEntity for WorkAnyAuthorships { type KeyType = usize; }

impl VariableSizeAttribute for WorkAnyAuthorships { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for WorkAnyAuthorships { const NS: & str = "a2_init_atts"; }

impl Entity for WorkBiblios { type T = crate::biblo_var_att::BiblioInfo; const N: usize = 75090099; const NAME: & str = "work-biblios"; }

impl MappableEntity for WorkBiblios { type KeyType = usize; }

impl VariableSizeAttribute for WorkBiblios { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for WorkBiblios { const NS: & str = "a2_init_atts"; }

impl Entity for WorkYears { type T = u8; const N: usize = 75090099; const NAME: & str = "work-years"; }

impl MappableEntity for WorkYears { type KeyType = usize; }

impl NamespacedEntity for WorkYears { const NS: & str = "a2_init_atts"; }

impl Link for WorkYears { type Source = crate::gen::a1_entity_mapping::Works; type Target = crate::steps::a1_entity_mapping::Years; }

impl Entity for WorksNames { type T = String; const N: usize = 75090099; const NAME: & str = "works-names"; }

impl MappableEntity for WorksNames { type KeyType = usize; }

impl VariableSizeAttribute for WorksNames { type SizeType = u16; type LocType = u64; }

impl NamespacedEntity for WorksNames { const NS: & str = "a2_init_atts"; }

impl MarkedAttribute<crate::common::NameMarker> for crate::gen::a1_entity_mapping::Works { type AttributeEntity = WorksNames; }

impl Entity for WorkDois { type T = String; const N: usize = 75090099; const NAME: & str = "work-dois"; }

impl MappableEntity for WorkDois { type KeyType = usize; }

impl VariableSizeAttribute for WorkDois { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for WorkDois { const NS: & str = "a2_init_atts"; }

impl MarkedAttribute<crate::common::DoiMarker> for crate::gen::a1_entity_mapping::Works { type AttributeEntity = WorkDois; }

impl Entity for CountriesNames { type T = String; const N: usize = 230; const NAME: & str = "countries-names"; }

impl MappableEntity for CountriesNames { type KeyType = usize; }

impl VariableSizeAttribute for CountriesNames { type SizeType = u8; type LocType = u16; }

impl NamespacedEntity for CountriesNames { const NS: & str = "a2_init_atts"; }

impl MarkedAttribute<crate::common::NameMarker> for crate::gen::a1_entity_mapping::Countries { type AttributeEntity = CountriesNames; }

impl Entity for CitiesNames { type T = String; const N: usize = 14805; const NAME: & str = "cities-names"; }

impl MappableEntity for CitiesNames { type KeyType = usize; }

impl VariableSizeAttribute for CitiesNames { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for CitiesNames { const NS: & str = "a2_init_atts"; }

impl MarkedAttribute<crate::common::NameMarker> for crate::gen::a1_entity_mapping::Cities { type AttributeEntity = CitiesNames; }

impl Entity for InstitutionsNames { type T = String; const N: usize = 30283; const NAME: & str = "institutions-names"; }

impl MappableEntity for InstitutionsNames { type KeyType = usize; }

impl VariableSizeAttribute for InstitutionsNames { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for InstitutionsNames { const NS: & str = "a2_init_atts"; }

impl MarkedAttribute<crate::common::NameMarker> for crate::gen::a1_entity_mapping::Institutions { type AttributeEntity = InstitutionsNames; }

impl Entity for CountryCodes { type T = [u8; 2]; const N: usize = 230; const NAME: & str = "country-codes"; }

impl MappableEntity for CountryCodes { type KeyType = usize; }

impl NamespacedEntity for CountryCodes { const NS: & str = "a2_init_atts"; }

impl Entity for CountryCodesThree { type T = [u8; 3]; const N: usize = 230; const NAME: & str = "country-codes-three"; }

impl MappableEntity for CountryCodesThree { type KeyType = usize; }

impl NamespacedEntity for CountryCodesThree { const NS: & str = "a2_init_atts"; }

impl Entity for InstLocs { type T = (f64, f64); const N: usize = 30283; const NAME: & str = "inst-locs"; }

impl MappableEntity for InstLocs { type KeyType = usize; }

impl NamespacedEntity for InstLocs { const NS: & str = "a2_init_atts"; }

impl Entity for InstRors { type T = [u8; 9]; const N: usize = 30283; const NAME: & str = "inst-rors"; }

impl MappableEntity for InstRors { type KeyType = usize; }

impl NamespacedEntity for InstRors { const NS: & str = "a2_init_atts"; }

impl Entity for InstCities { type T = u16; const N: usize = 30283; const NAME: & str = "inst-cities"; }

impl MappableEntity for InstCities { type KeyType = usize; }

impl NamespacedEntity for InstCities { const NS: & str = "a2_init_atts"; }

impl Entity for DiscardedAuthorsNames { type T = String; const N: usize = 100905485; const NAME: & str = "discarded-authors-names"; }

impl MappableEntity for DiscardedAuthorsNames { type KeyType = usize; }

impl VariableSizeAttribute for DiscardedAuthorsNames { type SizeType = u16; type LocType = u32; }

impl NamespacedEntity for DiscardedAuthorsNames { const NS: & str = "a2_init_atts"; }

impl MarkedAttribute<crate::common::NameMarker> for crate::gen::a1_entity_mapping::DiscardedAuthors { type AttributeEntity = DiscardedAuthorsNames; }

impl Entity for AuthorsNames { type T = String; const N: usize = 4037517; const NAME: & str = "authors-names"; }

impl MappableEntity for AuthorsNames { type KeyType = usize; }

impl VariableSizeAttribute for AuthorsNames { type SizeType = u16; type LocType = u32; }

impl NamespacedEntity for AuthorsNames { const NS: & str = "a2_init_atts"; }

impl MarkedAttribute<crate::common::NameMarker> for crate::gen::a1_entity_mapping::Authors { type AttributeEntity = AuthorsNames; }

impl Entity for AuthorWikiSlugs { type T = String; const N: usize = 4037517; const NAME: & str = "author-wiki-slugs"; }

impl MappableEntity for AuthorWikiSlugs { type KeyType = usize; }

impl VariableSizeAttribute for AuthorWikiSlugs { type SizeType = u8; type LocType = u16; }

impl NamespacedEntity for AuthorWikiSlugs { const NS: & str = "a2_init_atts"; }

impl Entity for AuthorOrcids { type T = [u8; 19]; const N: usize = 4037517; const NAME: & str = "author-orcids"; }

impl MappableEntity for AuthorOrcids { type KeyType = usize; }

impl NamespacedEntity for AuthorOrcids { const NS: & str = "a2_init_atts"; }

impl Entity for AuthorRawCites { type T = u32; const N: usize = 4037517; const NAME: & str = "author-raw-cites"; }

impl MappableEntity for AuthorRawCites { type KeyType = usize; }

impl NamespacedEntity for AuthorRawCites { const NS: & str = "a2_init_atts"; }

impl Entity for AuthorRawWorkCounts { type T = u32; const N: usize = 4037517; const NAME: & str = "author-raw-work-counts"; }

impl MappableEntity for AuthorRawWorkCounts { type KeyType = usize; }

impl NamespacedEntity for AuthorRawWorkCounts { const NS: & str = "a2_init_atts"; }

impl Entity for DomainsNames { type T = String; const N: usize = 6; const NAME: & str = "domains-names"; }

impl MappableEntity for DomainsNames { type KeyType = usize; }

impl VariableSizeAttribute for DomainsNames { type SizeType = u8; type LocType = u8; }

impl NamespacedEntity for DomainsNames { const NS: & str = "a2_init_atts"; }

impl MarkedAttribute<crate::common::NameMarker> for crate::gen::a1_entity_mapping::Domains { type AttributeEntity = DomainsNames; }

impl Entity for FieldsNames { type T = String; const N: usize = 28; const NAME: & str = "fields-names"; }

impl MappableEntity for FieldsNames { type KeyType = usize; }

impl VariableSizeAttribute for FieldsNames { type SizeType = u8; type LocType = u16; }

impl NamespacedEntity for FieldsNames { const NS: & str = "a2_init_atts"; }

impl MarkedAttribute<crate::common::NameMarker> for crate::gen::a1_entity_mapping::Fields { type AttributeEntity = FieldsNames; }

impl Entity for SubfieldsNames { type T = String; const N: usize = 254; const NAME: & str = "subfields-names"; }

impl MappableEntity for SubfieldsNames { type KeyType = usize; }

impl VariableSizeAttribute for SubfieldsNames { type SizeType = u8; type LocType = u16; }

impl NamespacedEntity for SubfieldsNames { const NS: & str = "a2_init_atts"; }

impl MarkedAttribute<crate::common::NameMarker> for crate::gen::a1_entity_mapping::Subfields { type AttributeEntity = SubfieldsNames; }

impl Entity for SourcesNames { type T = String; const N: usize = 40060; const NAME: & str = "sources-names"; }

impl MappableEntity for SourcesNames { type KeyType = usize; }

impl VariableSizeAttribute for SourcesNames { type SizeType = u16; type LocType = u32; }

impl NamespacedEntity for SourcesNames { const NS: & str = "a2_init_atts"; }

impl MarkedAttribute<crate::common::NameMarker> for crate::gen::a1_entity_mapping::Sources { type AttributeEntity = SourcesNames; }

impl Entity for TopicsNames { type T = String; const N: usize = 4518; const NAME: & str = "topics-names"; }

impl MappableEntity for TopicsNames { type KeyType = usize; }

impl VariableSizeAttribute for TopicsNames { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for TopicsNames { const NS: & str = "a2_init_atts"; }

impl MarkedAttribute<crate::common::NameMarker> for crate::gen::a1_entity_mapping::Topics { type AttributeEntity = TopicsNames; }

impl Entity for InstitutionsNameExts { type T = String; const N: usize = 30283; const NAME: & str = "institutions-name-exts"; }

impl MappableEntity for InstitutionsNameExts { type KeyType = usize; }

impl VariableSizeAttribute for InstitutionsNameExts { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for InstitutionsNameExts { const NS: & str = "a2_init_atts"; }

impl MarkedAttribute<crate::common::NameExtensionMarker> for crate::gen::a1_entity_mapping::Institutions { type AttributeEntity = InstitutionsNameExts; }

impl Entity for SourcesNameExts { type T = String; const N: usize = 40060; const NAME: & str = "sources-name-exts"; }

impl MappableEntity for SourcesNameExts { type KeyType = usize; }

impl VariableSizeAttribute for SourcesNameExts { type SizeType = u16; type LocType = u32; }

impl NamespacedEntity for SourcesNameExts { const NS: & str = "a2_init_atts"; }

impl MarkedAttribute<crate::common::NameExtensionMarker> for crate::gen::a1_entity_mapping::Sources { type AttributeEntity = SourcesNameExts; }

impl Entity for SubfieldsWikipedia { type T = String; const N: usize = 254; const NAME: & str = "subfields-wikipedia"; }

impl MappableEntity for SubfieldsWikipedia { type KeyType = usize; }

impl VariableSizeAttribute for SubfieldsWikipedia { type SizeType = u8; type LocType = u16; }

impl NamespacedEntity for SubfieldsWikipedia { const NS: & str = "a2_init_atts"; }

impl Entity for TopicsWikipedia { type T = String; const N: usize = 4518; const NAME: & str = "topics-wikipedia"; }

impl MappableEntity for TopicsWikipedia { type KeyType = usize; }

impl VariableSizeAttribute for TopicsWikipedia { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for TopicsWikipedia { const NS: & str = "a2_init_atts"; }

impl Entity for AuthorsNameExts { type T = String; const N: usize = 4037516; const NAME: & str = "authors-name-exts"; }

impl MappableEntity for AuthorsNameExts { type KeyType = usize; }

impl VariableSizeAttribute for AuthorsNameExts { type SizeType = u8; type LocType = u8; }

impl NamespacedEntity for AuthorsNameExts { const NS: & str = "a2_init_atts"; }

impl MarkedAttribute<crate::common::NameExtensionMarker> for crate::gen::a1_entity_mapping::Authors { type AttributeEntity = AuthorsNameExts; }

impl Entity for CountriesNameExts { type T = String; const N: usize = 229; const NAME: & str = "countries-name-exts"; }

impl MappableEntity for CountriesNameExts { type KeyType = usize; }

impl VariableSizeAttribute for CountriesNameExts { type SizeType = u8; type LocType = u8; }

impl NamespacedEntity for CountriesNameExts { const NS: & str = "a2_init_atts"; }

impl MarkedAttribute<crate::common::NameExtensionMarker> for crate::gen::a1_entity_mapping::Countries { type AttributeEntity = CountriesNameExts; }

impl Entity for SubfieldsNameExts { type T = String; const N: usize = 253; const NAME: & str = "subfields-name-exts"; }

impl MappableEntity for SubfieldsNameExts { type KeyType = usize; }

impl VariableSizeAttribute for SubfieldsNameExts { type SizeType = u8; type LocType = u8; }

impl NamespacedEntity for SubfieldsNameExts { const NS: & str = "a2_init_atts"; }

impl MarkedAttribute<crate::common::NameExtensionMarker> for crate::gen::a1_entity_mapping::Subfields { type AttributeEntity = SubfieldsNameExts; }

impl Entity for SourceYearQs { type T = u8; const N: usize = 1712400; const NAME: & str = "source-year-qs"; }

impl MappableEntity for SourceYearQs { type KeyType = (u16, u8); }

impl NamespacedEntity for SourceYearQs { const NS: & str = "a2_init_atts"; }

impl Entity for InstCountries { type T = u8; const N: usize = 30283; const NAME: & str = "inst-countries"; }

impl MappableEntity for InstCountries { type KeyType = usize; }

impl NamespacedEntity for InstCountries { const NS: & str = "a2_init_atts"; }

impl Link for InstCountries { type Source = crate::gen::a1_entity_mapping::Institutions; type Target = crate::gen::a1_entity_mapping::Countries; }

impl Entity for SubfieldAncestors { type T = u8; const N: usize = 254; const NAME: & str = "subfield-ancestors"; }

impl MappableEntity for SubfieldAncestors { type KeyType = usize; }

impl NamespacedEntity for SubfieldAncestors { const NS: & str = "a2_init_atts"; }

impl Link for SubfieldAncestors { type Source = crate::gen::a1_entity_mapping::Subfields; type Target = crate::gen::a1_entity_mapping::Fields; }

impl Entity for FieldAncestors { type T = u8; const N: usize = 28; const NAME: & str = "field-ancestors"; }

impl MappableEntity for FieldAncestors { type KeyType = usize; }

impl NamespacedEntity for FieldAncestors { const NS: & str = "a2_init_atts"; }

impl Link for FieldAncestors { type Source = crate::gen::a1_entity_mapping::Fields; type Target = crate::gen::a1_entity_mapping::Domains; }

impl Entity for TopicSubfields { type T = u8; const N: usize = 4518; const NAME: & str = "topic-subfields"; }

impl MappableEntity for TopicSubfields { type KeyType = usize; }

impl NamespacedEntity for TopicSubfields { const NS: & str = "a2_init_atts"; }

impl Link for TopicSubfields { type Source = crate::gen::a1_entity_mapping::Topics; type Target = crate::gen::a1_entity_mapping::Subfields; }

impl Entity for SourceAreaFields { type T = Box<[u8]>; const N: usize = 40060; const NAME: & str = "source-area-fields"; }

impl MappableEntity for SourceAreaFields { type KeyType = usize; }

impl VariableSizeAttribute for SourceAreaFields { type SizeType = u8; type LocType = u8; }

impl NamespacedEntity for SourceAreaFields { const NS: & str = "a2_init_atts"; }

impl Link for SourceAreaFields { type Source = crate::gen::a1_entity_mapping::Sources; type Target = crate::gen::a1_entity_mapping::AreaFields; }

impl Entity for WorkReferences { type T = Box<[u32]>; const N: usize = 75090099; const NAME: & str = "work-references"; }

impl MappableEntity for WorkReferences { type KeyType = usize; }

impl VariableSizeAttribute for WorkReferences { type SizeType = u16; type LocType = u32; }

impl NamespacedEntity for WorkReferences { const NS: & str = "a2_init_atts"; }

impl Link for WorkReferences { type Source = crate::gen::a1_entity_mapping::Works; type Target = crate::gen::a1_entity_mapping::Works; }

impl Entity for WorkSources { type T = Box<[u16]>; const N: usize = 75090099; const NAME: & str = "work-sources"; }

impl MappableEntity for WorkSources { type KeyType = usize; }

impl VariableSizeAttribute for WorkSources { type SizeType = u16; type LocType = u32; }

impl NamespacedEntity for WorkSources { const NS: & str = "a2_init_atts"; }

impl Link for WorkSources { type Source = crate::gen::a1_entity_mapping::Works; type Target = crate::gen::a1_entity_mapping::Sources; }

impl Entity for WorkTopics { type T = Box<[u16]>; const N: usize = 75090099; const NAME: & str = "work-topics"; }

impl MappableEntity for WorkTopics { type KeyType = usize; }

impl VariableSizeAttribute for WorkTopics { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for WorkTopics { const NS: & str = "a2_init_atts"; }

impl Link for WorkTopics { type Source = crate::gen::a1_entity_mapping::Works; type Target = crate::gen::a1_entity_mapping::Topics; }