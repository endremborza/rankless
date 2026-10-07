use wiretypes::wire;

pub const FINAL_YEAR: u16 = 2026;
pub const START_YEAR: u16 = 1950;
#[wire]
pub const MIN_PAPERS_FOR_INST: u16 = 250;
#[wire]
pub const MIN_PAPERS_FOR_SOURCE: u16 = 200;
#[wire]
pub const MIN_AUTHOR_WORK_COUNT: u16 = 8;
#[wire]
pub const MIN_AUTHOR_CITE_COUNT: u16 = 400;
pub const RANKLESS_ENV: &str = "full";
