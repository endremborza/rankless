// Cross-language type boundary:
//
// GET /v1/works-intersect/*spec (TS → Rust): a WorkSetQuery is a CNF (AND of OR-clauses) encoded
//   into the URL path — '/' separates AND-clauses, ',' separates OR-operands, ':' separates the
//   entity type from its ids. Each clause ORs ids of a single entity type; clauses are ANDed.
//   Parsed by rankless_server/src/handlers/works.rs — `intersect_get`.
//   The response is a PaginatedPaperSetResp (see tree-types.ts).

export type WorkSetClause = { etype: string; ids: string[] }; // OR over same-type entity ids
export type WorkSetQuery = WorkSetClause[]; // AND over clauses
