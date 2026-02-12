-- This view flattens the relationship between a work and its citations 
-- along with the key attributes needed for the 'breakdowns'.
CREATE OR REPLACE VIEW impact_denormalized AS
SELECT 
    -- Source Side Info (The original papers)
    w_src.id AS src_work_id,
    wa_src.author AS src_authors,
    wa_src.institution AS src_institutions,
    ins_src.country_code AS src_countries,
    wl_src.source AS src_sources,
    wt_src.id AS src_topics,
    top_src.subfield AS src_subfields,
    
    -- Citing Side Info (The papers that cited the source)
    w_cit.id AS cit_work_id,
    wa_cit.author AS cit_authors,
    wa_cit.institution AS cit_institutions,
    ins_cit.country_code AS cit_countries,
    wl_cit.source AS cit_sources,
    wt_cit.id AS cit_topics,
    top_cit.subfield AS cit_subfields

FROM works w_src
-- Join citations (referenced_work_id is the source, parent_id is the citer)
LEFT JOIN "works-referenced_works" wrw ON w_src.id = wrw.referenced_work_id
LEFT JOIN works w_cit ON wrw.parent_id = w_cit.id

-- Source Metadata Joins
LEFT JOIN "works-authorships" wa_src ON w_src.id = wa_src.parent_id
LEFT JOIN institutions ins_src ON wa_src.institution = ins_src.id
LEFT JOIN "works-locations" wl_src ON w_src.id = wl_src.parent_id
LEFT JOIN "works-topics" wt_src ON w_src.id = wt_src.parent_id
LEFT JOIN topics top_src ON wt_src.id = top_src.id

-- Citing Metadata Joins
LEFT JOIN "works-authorships" wa_cit ON w_cit.id = wa_cit.parent_id
LEFT JOIN institutions ins_cit ON wa_cit.institution = ins_cit.id
LEFT JOIN "works-locations" wl_cit ON w_cit.id = wl_cit.parent_id
LEFT JOIN "works-topics" wt_cit ON w_cit.id = wt_cit.parent_id
LEFT JOIN topics top_cit ON wt_cit.id = top_cit.id;
