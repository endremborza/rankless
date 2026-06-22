import type { RequestHandler } from './$types';

// OpenSearch descriptor so browsers can add Rankless as a search engine. Points at the /search page,
// which resolves {searchTerms} against the union search and renders the results list.
export const GET: RequestHandler = ({ url }) => {
	const origin = url.origin;
	const xml = `<?xml version="1.0" encoding="UTF-8"?>
<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/" xmlns:moz="http://www.mozilla.org/2006/browser/search/">
	<ShortName>Rankless</ShortName>
	<Description>Search authors, institutions, journals, countries and research fields on Rankless</Description>
	<InputEncoding>UTF-8</InputEncoding>
	<Image width="16" height="16" type="image/png">${origin}/favicon.png</Image>
	<Url type="text/html" method="get" template="${origin}/search?q={searchTerms}" />
	<moz:SearchForm>${origin}/search</moz:SearchForm>
</OpenSearchDescription>
`;
	return new Response(xml, {
		headers: {
			'Content-Type': 'application/opensearchdescription+xml',
			'Cache-Control': 'public, max-age=86400'
		}
	});
};
