use dmove::Entity;
use rankless_rs::gen::a1_entity_mapping::Subfields;

pub const MAX_HITS: usize = 80;
pub const STAMP_FNAME: &str = "stamp";
pub const PORT: u16 = 3038;
pub const SEARCH_SIZE: usize = 20;
pub const MAX_SLICE: usize = 40_000;
pub const MAX_SHALLOW_IDS: usize = 64;
pub const CACHEABLE_FROM: u32 = 10_000;
pub const DEFAULT_N_THREADS: usize = 16;
pub const N_SUBFIELDS: usize = Subfields::N;
pub const WORKS_PAGE_SIZE_MAX: usize = 400;

pub const INTERSECT_MAX_CLAUSES: usize = 8;
pub const INTERSECT_MAX_OPERANDS: usize = 32;
pub const INTERSECT_MAX_BASE: usize = 100_000;
pub const INTERSECT_DEFAULT_N: usize = 200;

pub const FIN_UNIS: [&str; 2] = ["budapesti-corvinus-egyetem", "tse"];

pub const FIN_SOURCES: [&str; 50] = [
    "psychological-review",
    "water-research",
    "journal-of-the-econometric-society",
    "technometrics",
    "tpami",
    "biomaterials",
    "child-development",
    "journal-of-fluid-mechanics",
    "ajcn",
    "tree",
    "strategic-management-journal",
    "nuclear-physics-b",
    "american-journal-of-psychiatry",
    "american-chemical-society-nano",
    "neuro-image",
    "geochimica-et-cosmochimica-acta",
    "jci",
    "ecology-ecological-society-of-america",
    "journal-of-marketing",
    "contemporary-sociology-a-journal-of-reviews",
    "apl-on-cdrom",
    "journal-of-financial-economics",
    "annalsorg",
    "american-economic-review",
    "jbc",
    "blood",
    "rmp-online",
    "academy-of-management-review",
    "es-t",
    "jgr",
    "jneurosci",
    "jem-online",
    "journal-of-the-american-statistical-association",
    "apj",
    "psychol-bull",
    "nature-materials",
    "journal-of-clinical-oncology",
    "neuron",
    "the-journal-of-finance",
    "angewandte-chemie-international-edition",
    "journal-of-personality-social-psychology",
    "advanced-energy-materials",
    "circulation",
    "csr",
    "the-lancet",
    "prl",
    "chemical-reviews",
    "nejm",
    "science",
    "nature",
];

pub const FIN_AUTHORS: [&str; 79] = [
    "david-baker",           // Chemistry
    "james-p-allison",       // Physiology or Medicine
    "frances-h-arnold",      // Chemistry
    "jean-tirole",           // Prize in Economic Sciences
    "paul-milgrom",          // Prize in Economic Sciences
    "benjamin-list",         // Chemistry
    "andrew-fire",           // Physiology or Medicine
    "angus-deaton",          // Prize in Economic Sciences
    "ben-bernanke",          // Prize in Economic Sciences
    "david-card",            // Prize in Economic Sciences
    "eric-betzig",           // Chemistry
    "roger-penrose",         // Physics
    "alvin-e-roth",          // Prize in Economic Sciences
    "jeffrey-c-hall",        // Physiology or Medicine
    "john-c-mather",         // Physics
    "william-c-campbell",    // Physiology or Medicine
    "leonid-hurwicz",        // Prize in Economic Sciences
    "paul-krugman",          // Prize in Economic Sciences
    "francois-englert",      // Physics
    "peter-j-ratcliffe",     // Physiology or Medicine
    "gregg-l-semenza",       // Physiology or Medicine
    "carol-w-greider",       // Physiology or Medicine
    "lloyd-s-shapley",       // Prize in Economic Sciences
    "makoto-kobayashi",      // Physics
    "philip-h-dybvig",       // Prize in Economic Sciences
    "shinya-yamanaka",       // Physiology or Medicine
    "charles-m-rice",        // Physiology or Medicine
    "shuji-nakamura",        // Physics
    "demis-hassabis",        // Chemistry
    "michael-levitt",        // Chemistry
    "luc-montagnier",        // Physiology or Medicine
    "syukuro-manabe",        // Physics
    "martin-chalfie",        // Chemistry
    "michael-kremer",        // Prize in Economic Sciences
    "peter-w-higgs",         // Physics
    "louis-e-brus",          // Chemistry
    "arieh-warshel",         // Chemistry
    "ferenc-krausz",         // Physics
    "joachim-frank",         // Chemistry
    "drew-weissman",         // Physiology or Medicine
    "tasuku-honjo",          // Physiology or Medicine
    "akira-suzuki",          // Chemistry
    "esther-duflo",          // Prize in Economic Sciences
    "george-smith",          // Chemistry
    "gary-ruvkun",           // Physiology or Medicine
    "aziz-sancar",           // Chemistry
    "greg-winter",           // Chemistry
    "eric-maskin",           // Prize in Economic Sciences
    "paul-romer",            // Prize in Economic Sciences
    "ada-yonath",            // Chemistry
    "jeanpierre-sauvage",    // Chemistry
    "daron-acemoglu",        // Prize in Economic Sciences
    "elizabeth-h-blackburn", // Physiology or Medicine
    "john-okeefe",           // Physiology or Medicine
    "carolyn-r-bertozzi",    // Chemistry
    "william-d-nordhaus",    // Prize in Economic Sciences
    "moungi-g-bawendi",      // Chemistry
    "richard-h-thaler",      // Prize in Economic Sciences
    "maybritt-moser",        // Physiology or Medicine
    "eiichi-negishi",        // Chemistry
    "george-p-smith",        // Physics
    "edmund-s-phelps",       // Prize in Economic Sciences
    "richard-a-henderson",   // Chemistry
    "edvard-i-moser",        // Physiology or Medicine
    "geoffrey-e-hinton",     // Physics
    "douglas-w-diamond",     // Prize in Economic Sciences
    "stefan-heller",         // Chemistry
    "randy-schekman",        // Physiology or Medicine
    "joshua-d-angrist",      // Prize in Economic Sciences
    "duncan-w-haldane",      // Physics
    "rainer-weiss",          // Physics
    "morten-meldal",         // Chemistry
    "peter-diamond",         // Prize in Economic Sciences
    "brian-l-schmidt",       // Physics
    "guido-w-imbens",        // Prize in Economic Sciences
    "george-f-smoot",        // Physics
    "craig-c-mello",         // Physiology or Medicine
    "john-jumper",           // Chemistryy
    "elinor-ostrom",         // Prize in Economic Sciences
];
