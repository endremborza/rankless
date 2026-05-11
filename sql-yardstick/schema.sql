CREATE TABLE authors (
	id BIGINT NOT NULL, 
	orcid TEXT, 
	display_name TEXT, 
	CONSTRAINT authors_pkey PRIMARY KEY (id)
);
CREATE TABLE domains (
	id BIGINT NOT NULL, 
	display_name TEXT, 
	CONSTRAINT domains_pkey PRIMARY KEY (id)
);
CREATE TABLE institutions (
	id BIGINT NOT NULL, 
	display_name TEXT, 
	country_code TEXT, 
	display_name_acronyms TEXT, 
	CONSTRAINT institutions_pkey PRIMARY KEY (id)
);
CREATE TABLE sources (
	id BIGINT NOT NULL, 
	display_name TEXT, 
	CONSTRAINT sources_pkey PRIMARY KEY (id)
);
CREATE TABLE works (
	id BIGINT NOT NULL, 
	doi TEXT, 
	title TEXT, 
	display_name TEXT, 
	publication_year BIGINT, 
	type TEXT, 
	CONSTRAINT works_pkey PRIMARY KEY (id)
);
CREATE TABLE fields (
	id BIGINT NOT NULL, 
	display_name TEXT, 
	domain BIGINT, 
	CONSTRAINT fields_pkey PRIMARY KEY (id), 
	CONSTRAINT fields_domain_domains_fkey FOREIGN KEY(domain) REFERENCES domains (id)
);
CREATE TABLE "works-authorships" (
	parent_id BIGINT, 
	author BIGINT, 
	institution BIGINT, 
	CONSTRAINT "works-authorships_author_authors_fkey" FOREIGN KEY(author) REFERENCES authors (id), 
	CONSTRAINT "works-authorships_institution_institutions_fkey" FOREIGN KEY(institution) REFERENCES institutions (id), 
	CONSTRAINT "works-authorships_parent_id_works_fkey" FOREIGN KEY(parent_id) REFERENCES works (id)
);
CREATE TABLE "works-locations" (
	parent_id BIGINT, 
	source BIGINT, 
	CONSTRAINT "works-locations_parent_id_works_fkey" FOREIGN KEY(parent_id) REFERENCES works (id), 
	CONSTRAINT "works-locations_source_sources_fkey" FOREIGN KEY(source) REFERENCES sources (id)
);
CREATE TABLE "works-referenced_works" (
	parent_id BIGINT, 
	referenced_work_id BIGINT, 
	CONSTRAINT "works-referenced_works_parent_id_works_fkey" FOREIGN KEY(parent_id) REFERENCES works (id), 
	CONSTRAINT "works-referenced_works_referenced_work_id_works_fkey" FOREIGN KEY(referenced_work_id) REFERENCES works (id)
);
CREATE TABLE "works-topics" (
	parent_id BIGINT, 
	id BIGINT, 
	score DOUBLE PRECISION, 
	CONSTRAINT "works-topics_parent_id_works_fkey" FOREIGN KEY(parent_id) REFERENCES works (id)
);
CREATE TABLE subfields (
	id BIGINT NOT NULL, 
	display_name TEXT, 
	field BIGINT, 
	CONSTRAINT subfields_pkey PRIMARY KEY (id), 
	CONSTRAINT subfields_field_fields_fkey FOREIGN KEY(field) REFERENCES fields (id)
);
CREATE TABLE topics (
	id BIGINT NOT NULL, 
	display_name TEXT, 
	subfield BIGINT, 
	field BIGINT, 
	domain BIGINT, 
	CONSTRAINT topics_pkey PRIMARY KEY (id), 
	CONSTRAINT topics_domain_domains_fkey FOREIGN KEY(domain) REFERENCES domains (id), 
	CONSTRAINT topics_field_fields_fkey FOREIGN KEY(field) REFERENCES fields (id), 
	CONSTRAINT topics_subfield_subfields_fkey FOREIGN KEY(subfield) REFERENCES subfields (id)
);
