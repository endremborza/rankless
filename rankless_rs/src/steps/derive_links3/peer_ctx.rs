use dmove::{Entity, UnsignedNumber, ET, MAA};

use crate::{
    common::{init_empty_slice, CitSubfieldsArrayMarker},
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields},
        a2_init_atts::{InstCountries, InstLocs, WorkYears},
        derive_links2::AuthorWorks,
    },
    peers::{self, PeerCalculator},
    steps::a1_entity_mapping::Years,
    QuickestBox, ReadIter, Stowage,
};

pub const N_PEER_SF_DIMS: usize = 10;
pub const W_PEER_SF: f64 = 1.0;
pub const W_PEER_RATE: f64 = 0.5;
pub const W_PEER_GEO: f64 = 0.3;
pub const W_PEER_COUNTRY: f64 = 0.5;
pub const W_PEER_TEMPORAL: f64 = 0.4;

const K_TREE: usize = 500;

pub(super) type InstCitSfsArr = ET<MAA<Institutions, CitSubfieldsArrayMarker>>;
pub(super) type SfCitSfsArr = ET<MAA<Subfields, CitSubfieldsArrayMarker>>;
pub(super) type CountryCitSfsArr = ET<MAA<Countries, CitSubfieldsArrayMarker>>;
pub(super) type SourceCitSfsArr = ET<MAA<Sources, CitSubfieldsArrayMarker>>;
pub(super) type AuthorCitSfsArr = ET<MAA<Authors, CitSubfieldsArrayMarker>>;

pub(super) struct InstPeerCtx {
    pub filter: Vec<bool>,
    pub cit_sfs: Box<[InstCitSfsArr]>,
    pub top_sfs: Vec<[usize; N_PEER_SF_DIMS]>,
    pub sf_totals: Vec<f64>,
    pub locs: Box<[(f64, f64)]>,
    pub countries: Box<[ET<InstCountries>]>,
    pub sf_weights: [f64; N_PEER_SF_DIMS],
}

pub struct AuthorPeerCtx {
    pub filter: Vec<bool>,
    pub cit_sfs: Box<[AuthorCitSfsArr]>,
    pub top_sfs: Vec<[usize; N_PEER_SF_DIMS]>,
    pub career_centroids: Vec<f32>,
    pub sf_weights: [f64; N_PEER_SF_DIMS],
}

pub(super) struct SfPeerCtx {
    pub filter: Vec<bool>,
    pub cit_sfs: Box<[SfCitSfsArr]>,
    pub top_sfs: Vec<[usize; N_PEER_SF_DIMS]>,
    pub sf_weights: [f64; N_PEER_SF_DIMS],
}

pub(super) struct CountryPeerCtx {
    pub filter: Vec<bool>,
    pub cit_sfs: Box<[CountryCitSfsArr]>,
    pub top_sfs: Vec<[usize; N_PEER_SF_DIMS]>,
    pub sf_weights: [f64; N_PEER_SF_DIMS],
}

pub(super) struct SourcePeerCtx {
    pub filter: Vec<bool>,
    pub cit_sfs: Box<[SourceCitSfsArr]>,
    pub top_sfs: Vec<[usize; N_PEER_SF_DIMS]>,
    pub sf_totals: Vec<f64>,
    pub sf_weights: [f64; N_PEER_SF_DIMS],
}

impl InstPeerCtx {
    pub(super) fn new(stowage: &Stowage, filter: Vec<bool>, _wcounts: &[usize]) -> Self {
        let cit_sfs =
            stowage.get_marked_interface::<Institutions, CitSubfieldsArrayMarker, QuickestBox>();
        let top_sfs = peers::compute_top_sfs(&*cit_sfs);
        let sf_totals = peers::compute_sf_totals(&*cit_sfs);
        let locs = stowage.get_entity_interface::<InstLocs, QuickestBox>();
        let countries = stowage.get_entity_interface::<InstCountries, QuickestBox>();
        Self {
            filter,
            cit_sfs,
            top_sfs,
            sf_totals,
            locs,
            countries,
            sf_weights: peers::sf_peer_weights(),
        }
    }
}

impl SfPeerCtx {
    pub(super) fn new(stowage: &Stowage, filter: Vec<bool>, _wcounts: &[usize]) -> Self {
        let cit_sfs =
            stowage.get_marked_interface::<Subfields, CitSubfieldsArrayMarker, QuickestBox>();
        let top_sfs = peers::compute_top_sfs(&*cit_sfs);
        Self {
            filter,
            cit_sfs,
            top_sfs,
            sf_weights: peers::sf_peer_weights(),
        }
    }
}

impl CountryPeerCtx {
    pub(super) fn new(stowage: &Stowage, filter: Vec<bool>, _wcounts: &[usize]) -> Self {
        let cit_sfs =
            stowage.get_marked_interface::<Countries, CitSubfieldsArrayMarker, QuickestBox>();
        let top_sfs = peers::compute_top_sfs(&*cit_sfs);
        Self {
            filter,
            cit_sfs,
            top_sfs,
            sf_weights: peers::sf_peer_weights(),
        }
    }
}

impl SourcePeerCtx {
    pub(super) fn new(stowage: &Stowage, filter: Vec<bool>, _wcounts: &[usize]) -> Self {
        let cit_sfs =
            stowage.get_marked_interface::<Sources, CitSubfieldsArrayMarker, QuickestBox>();
        let top_sfs = peers::compute_top_sfs(&*cit_sfs);
        let sf_totals = peers::compute_sf_totals(&*cit_sfs);
        Self {
            filter,
            cit_sfs,
            top_sfs,
            sf_totals,
            sf_weights: peers::sf_peer_weights(),
        }
    }
}

impl AuthorPeerCtx {
    pub fn new(
        stowage: &Stowage,
        filter: Vec<bool>,
        _wcounts: &[usize],
        w_years: &[ET<WorkYears>],
    ) -> Self {
        let cit_sfs =
            stowage.get_marked_interface::<Authors, CitSubfieldsArrayMarker, QuickestBox>();
        let top_sfs = peers::compute_top_sfs(&*cit_sfs);
        let mut career_centroids_o = init_empty_slice::<Authors, [Option<f32>; 1]>();
        for (aid, aworks) in stowage
            .get_entity_interface::<AuthorWorks, ReadIter>()
            .enumerate()
        {
            let mut yearly_papers = [0usize; Years::N + 1];
            for wid in aworks {
                let wind = w_years[wid.to_usize()].to_usize();
                yearly_papers[wind] += 1;
            }
            career_centroids_o[aid] = [peers::compute_career_centroid(&yearly_papers)];
        }
        let career_centroids = peers::normalize_opt_arr(career_centroids_o.to_vec())
            .into_iter()
            .map(|e| e[0])
            .collect();
        Self {
            filter,
            cit_sfs,
            top_sfs,
            career_centroids,
            sf_weights: peers::sf_peer_weights(),
        }
    }
}

impl PeerCalculator for InstPeerCtx {
    type E = Institutions;
    type EmbBasis = [f32; N_PEER_SF_DIMS];
    const EMBED_DIMS: usize = N_PEER_SF_DIMS;
    const N_CANDIDATES: usize = K_TREE;
    const N_PARTITIONS: usize = 10;

    fn get_embedding_basis(&self) -> Box<[Self::EmbBasis]> {
        peers::compute_log_pca_box(&self.cit_sfs, &self.filter)
    }

    fn final_distance_calc(&self, a: usize, b: usize) -> f64 {
        W_PEER_SF
            * peers::sf_log_dist(
                &self.cit_sfs[a],
                &self.cit_sfs[b],
                &self.top_sfs[a],
                &self.sf_weights,
            )
            + W_PEER_RATE
                * peers::sf_rate_dist(
                    &self.cit_sfs[a],
                    &self.cit_sfs[b],
                    &self.top_sfs[a],
                    self.sf_totals[a],
                    self.sf_totals[b],
                )
            + W_PEER_GEO * peers::geo_sq_dist(self.locs[a], self.locs[b])
            + W_PEER_COUNTRY
                * if self.countries[a] != self.countries[b] {
                    1.0
                } else {
                    0.0
                }
    }
}

impl PeerCalculator for SfPeerCtx {
    type E = Subfields;
    type EmbBasis = [f32; N_PEER_SF_DIMS];
    const EMBED_DIMS: usize = N_PEER_SF_DIMS;
    const N_CANDIDATES: usize = K_TREE;

    fn get_embedding_basis(&self) -> Box<[Self::EmbBasis]> {
        peers::compute_log_pca_box(&self.cit_sfs, &self.filter)
    }

    fn final_distance_calc(&self, a: usize, b: usize) -> f64 {
        W_PEER_SF
            * peers::sf_log_dist(
                &self.cit_sfs[a],
                &self.cit_sfs[b],
                &self.top_sfs[a],
                &self.sf_weights,
            )
    }
}

impl PeerCalculator for CountryPeerCtx {
    type E = Countries;
    type EmbBasis = [f32; N_PEER_SF_DIMS];
    const EMBED_DIMS: usize = N_PEER_SF_DIMS;
    const N_CANDIDATES: usize = K_TREE;

    fn get_embedding_basis(&self) -> Box<[Self::EmbBasis]> {
        peers::compute_log_pca_box(&self.cit_sfs, &self.filter)
    }

    fn final_distance_calc(&self, a: usize, b: usize) -> f64 {
        W_PEER_SF
            * peers::sf_log_dist(
                &self.cit_sfs[a],
                &self.cit_sfs[b],
                &self.top_sfs[a],
                &self.sf_weights,
            )
    }
}

impl PeerCalculator for SourcePeerCtx {
    type E = Sources;
    type EmbBasis = [f32; N_PEER_SF_DIMS];
    const EMBED_DIMS: usize = N_PEER_SF_DIMS;
    const N_CANDIDATES: usize = K_TREE;
    const N_PARTITIONS: usize = 10;

    fn get_embedding_basis(&self) -> Box<[Self::EmbBasis]> {
        peers::compute_log_pca_box(&self.cit_sfs, &self.filter)
    }

    fn final_distance_calc(&self, a: usize, b: usize) -> f64 {
        W_PEER_SF
            * peers::sf_log_dist(
                &self.cit_sfs[a],
                &self.cit_sfs[b],
                &self.top_sfs[a],
                &self.sf_weights,
            )
            + W_PEER_RATE
                * peers::sf_rate_dist(
                    &self.cit_sfs[a],
                    &self.cit_sfs[b],
                    &self.top_sfs[a],
                    self.sf_totals[a],
                    self.sf_totals[b],
                )
    }
}

impl PeerCalculator for AuthorPeerCtx {
    type E = Authors;
    type EmbBasis = [f32; N_PEER_SF_DIMS];
    const EMBED_DIMS: usize = N_PEER_SF_DIMS;
    const N_CANDIDATES: usize = K_TREE;

    fn get_embedding_basis(&self) -> Box<[Self::EmbBasis]> {
        peers::compute_log_pca_box(&self.cit_sfs, &self.filter)
    }

    fn final_distance_calc(&self, a: usize, b: usize) -> f64 {
        W_PEER_SF
            * peers::sf_log_dist(
                &self.cit_sfs[a],
                &self.cit_sfs[b],
                &self.top_sfs[a],
                &self.sf_weights,
            )
            + W_PEER_TEMPORAL * (self.career_centroids[a] - self.career_centroids[b]).powi(2) as f64
    }
}
