// Canonical forms of the two external identifiers the ledger joins on. Every DOI/ORCID
// entering the ledger (or looked up in the enrichment cache) passes through here, so the
// stored form is the canonical one and downstream matching is plain equality.
//
// Cross-language mirrors — keep the three in step:
//   pyscripts/ledger_ids.py         (review lane)
//   rankless_rs/src/user_ledger.rs  (pipeline: ledger claims ↔ works-CSV doi column)

export function canonicalDoi(doi: string): string {
	return doi
		.trim()
		.replace(/^https?:\/\/(dx\.)?doi\.org\//i, '')
		.toLowerCase();
}

export function normalizeOrcid(s: string): string {
	return s
		.trim()
		.replace(/^https?:\/\/(www\.)?orcid\.org\//i, '')
		.toUpperCase();
}
