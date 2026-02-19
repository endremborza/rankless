Based on an SQL schema, that is loaded to a Postgres db, I need a python script, that can generate a certain kind of output. The python script can use anything, pandas, sqlalchemy, the point is that is should utilize python tools and SQL but still be as efficient as possible. It can have a preprocessing step where it creates views in the database, before anything is run. The eventual form of the program should be a flask server, I will explain the API for that


## API:

### Request:

A request has 3 parameters


root_type: `RootType` (the type of entity the response tree is for, )
root_id: int
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


## Counting semantics (critical)

Both `linkCount` and `sourceCount` at any node must be **distinct** counts — not sums from children.

- **linkCount** at a node = number of DISTINCT `(source_work, citing_work)` citation-edge pairs where `source_work` satisfies ALL ancestor constraints AND is classified under this node's breakdown key.
- **sourceCount** at a node = number of DISTINCT `source_work` ids satisfying the same constraints.

A naive SUM of child counts will over-count whenever:
- A source work maps to multiple breakdown keys at the same level (e.g., a paper with two subfields, or an authorship from two institutions), or
- A source work has multiple citing works, each mapped to different children of the next level.

The correct model: at every level, re-compute counts from the raw `(source_work, citing_work)` edge set filtered by that level's constraint — do **not** roll up by summing children.

**Known bug in current `flask.py`**: The SQL query groups by all breakdown columns simultaneously and sums `COUNT(*)` as linkCount. When `rows_to_tree` accumulates these grouped rows up the tree, it adds rather than unions, causing higher-level nodes to over-count whenever branches intersect. The fix requires computing each level's counts independently from the raw impact edges, not by aggregating child rows.


## The SQL Schema:

in `schema.sql`
