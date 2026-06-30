# Unfinished / deferred features

Features that exist in the codebase (wholly or in part) but are **not shipping in the current
version** — kept here so they aren't lost between releases. None of these are reachable by users
on the live site; don't list them in the [v3 changelog](v2-to-v3-changes.md) or the homepage
showcase until they ship.

## Path to Person — built, not reachable

Traces the chain of citations connecting two scholars ("how an author's papers are cited by
another author's work"). The page, server loader, and backend path-finder all exist, but the
tool isn't linked or surfaced on the live site.

- `src/routes/path-to-person/` (`+page.svelte`, `[aidSrc]/[aidTarget]/{+page.svelte,+page.server.ts}`)
- `rankless_trees/src/path_finder.rs`
- (`src/routes/pathlogo/` + `PathLogo.svelte` is just a logo SVG, not part of this feature.)

## Browse tables — built, deferred

Sortable, filterable tabular listings of all entities of a type at `/[rootType]/table`. Complete
enough to render but deferred from this release.

- `src/routes/(stat)/[rootType]/table/{+page.svelte,+page.server.ts}`
- Backed by the existing `/slice/:etype/:from/:to` endpoint.

## Topic domination / leadership — partial

The **"★ originated <topic>"** flag _is_ live (shown in `PaperRainbow.svelte` for
`paper.createdTopic`). The broader **topic-leadership listing** (an entity's dominated topics) is
not: the component is uncommitted WIP and the data path is only partly wired.

- `src/lib/components/DominatedTopics.svelte` — **untracked** (never committed)
- `DominatedTopic` type in `src/lib/tree-types.ts`
- `TopicDominatorMarker` (`rankless_rs/src/common.rs`) + `rankless_rs/src/steps/derive_links3/topic_tags.rs`
