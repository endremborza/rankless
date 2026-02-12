Based on an SQL schema, that is loaded to a Postgres db, I need a python script, that can generate a certain kind of output. The python script can use anything, pandas, sqlalchemy, the point is that is should utilize python tools and SQL but still be as efficient as possible. It can have a preprocessing step where it creates views in the database, before anything is run. The eventual form of the program should be a flask server, I will explain the API for that


## API:

### Request:

A request has 2 parameters


root_type: `RootType` (the type of entity the response tree is for, )
breakdowns: `list[{node:NodeType, sourceSide:bool}]` (the breakdowns that result in the tree)

where the types correspond to 

```
type RootType = "authors" | "institutions" | "countries" | "sources" | "subfields"
type NodeType = RootType | "topics" | "works"
```


### Response

a response is a json of a tree-like structure


the type itself can be recursively defined like this: 

```
type TreeGen<T> = T & { children?: Record<string, TreeGen<T>> };
type ResponseNode = TreeGen<{
	linkCount: number;
	sourceCount: number;
}>;
```


For the response to be created, we need all the papers related to the root entity (written by author, institution that has affiliation for at least one author, country where one institution with that country code has authorship, etc), and all the corresponding papers citing these papers, properly organized. I will refer to this as the "impact body"

the sourceSide boolean part of a breakdown, that simply means weather the node part is related to the paper produced by the entity, or a paper citing a paper produced by the entity

the node part of the breadkdown is key, it means for each level (as the breakdowns parameter can be arbitrarily long, but it would be probably infeasible if longer than 3-4) what do we use to group the impact body. 

say breakdowns looks like this: `[{node: subfields, sourceSide: true}, {node: countries, sourceSide: false}]` while root_type is institutions. that would mean that on the first level of the response node children, a key for the record would be the id of a subfield that is used to categorize papers written by authors at that institution, and for the values: sourceCount would be the number of papers written by the institution categorized as the subfield corresponding to the key, while link count would be the number of citations these papers have received.
each of these subfield level children would have a number of children for countries that are author of papers that are on the citing side of the impact body, so the countries citing work done by the institution. and a key here is the country id (say, the country code), the sourceCount is the number of papers that have received at least one citation from this country, (while also being categorized as the subfield that is the parent of this child), the linkCount here is the number of citations that were made by papers written by this levels country, to papers that have the subfield categorization of this parent, (of course authored by authors at the institution in question)


## The SQL Schema:

here is the sql schema:

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
	abbreviated_title TEXT, 
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
	index BIGINT, 
	parent_id BIGINT, 
	author BIGINT, 
	institution BIGINT, 
	CONSTRAINT "works-authorships_author_authors_fkey" FOREIGN KEY(author) REFERENCES authors (id), 
	CONSTRAINT "works-authorships_institution_institutions_fkey" FOREIGN KEY(institution) REFERENCES institutions (id), 
	CONSTRAINT "works-authorships_parent_id_works_fkey" FOREIGN KEY(parent_id) REFERENCES works (id)
);
CREATE TABLE "works-locations" (
	index BIGINT, 
	parent_id BIGINT, 
	source BIGINT, 
	CONSTRAINT "works-locations_parent_id_works_fkey" FOREIGN KEY(parent_id) REFERENCES works (id), 
	CONSTRAINT "works-locations_source_sources_fkey" FOREIGN KEY(source) REFERENCES sources (id)
);
CREATE TABLE "works-referenced_works" (
	index BIGINT, 
	parent_id BIGINT, 
	referenced_work_id BIGINT, 
	CONSTRAINT "works-referenced_works_parent_id_works_fkey" FOREIGN KEY(parent_id) REFERENCES works (id), 
	CONSTRAINT "works-referenced_works_referenced_work_id_works_fkey" FOREIGN KEY(referenced_work_id) REFERENCES works (id)
);
CREATE TABLE "works-topics" (
	index BIGINT, 
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
