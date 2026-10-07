// How an author's works are paged from the backend. Free of SvelteKit virtual modules so the
// Playwright specs import it too.
export const INITIAL_PAGE_SIZE = 20;
export const WORKS_PAGE_SIZE = 200;
// Pages arrive ranked by citation count so the first screen is the entity's most-cited works and
// every appended page stays contiguous in that order (the backend re-sorts deterministically).
export const WORKS_SORT = 'citations';
