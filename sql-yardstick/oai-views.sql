
DROP MATERIALIZED VIEW IF EXISTS work_authors CASCADE;
CREATE MATERIALIZED VIEW work_authors AS
SELECT
    wa.parent_id AS work_id,
    wa.author,
    wa.institution,
    i.country_code
FROM "works-authorships" wa
LEFT JOIN institutions i ON wa.institution = i.id;


DROP MATERIALIZED VIEW IF EXISTS citation_edges CASCADE;
CREATE MATERIALIZED VIEW citation_edges AS
SELECT
    wr.referenced_work_id AS source_work,
    wr.parent_id AS citing_work
FROM "works-referenced_works" wr;


DROP MATERIALIZED VIEW IF EXISTS work_subfields CASCADE;
CREATE MATERIALIZED VIEW work_subfields AS
SELECT
    wt.parent_id AS work_id,
    t.subfield
FROM "works-topics" wt
JOIN topics t ON wt.id = t.id;


DROP MATERIALIZED VIEW IF EXISTS work_sources CASCADE;
CREATE MATERIALIZED VIEW work_sources AS
SELECT
    wl.parent_id AS work_id,
    wl.source
FROM "works-locations" wl;


CREATE INDEX ON citation_edges(source_work);
CREATE INDEX ON citation_edges(citing_work);
CREATE INDEX ON work_authors(work_id);
CREATE INDEX ON work_subfields(work_id);
CREATE INDEX ON work_sources(work_id);


