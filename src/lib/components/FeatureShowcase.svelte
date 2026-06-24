<script lang="ts">
	import showcaseRaw from '$lib/assets/data/homepage-showcase.json';
	import type { ShowcaseData } from '$lib/types/showcase';
	import ShowcasePeers from './ShowcasePeers.svelte';
	import ShowcaseCoauthors from './ShowcaseCoauthors.svelte';
	import ShowcaseExport from './ShowcaseExport.svelte';

	// Baked snapshot, shaped + validated by pyscripts/homepage_showcase.py (no backend call on load).
	const showcase = showcaseRaw as unknown as ShowcaseData;
	const { scholar, peers, coauthors, samplePaper } = showcase;
	const profile = `/authors/${scholar.semanticId}`;
</script>

<div class="card wide login">
	<span class="feature-name">Login</span>
	<div class="login-cols">
		<div>
			<h4>Claim your profile and correct your record.</h4>
			<p>
				Rankless builds author profiles automatically from open data, so the picture isn't always
				perfect. Sign in with your ORCID iD to take ownership of yours.
			</p>
		</div>
		<div>
			<p>
				Add missing papers, remove ones that aren't yours, and merge duplicate records. Every edit
				is written to a public, revocable ledger — your corrections, transparently tracked.
			</p>
			<a class="card-cta" href="/login?returnTo=/" data-sveltekit-preload-data="off"
				>Sign in with ORCID →</a
			>
		</div>
	</div>
</div>

<div class="feature-grid">
	<div class="card">
		<span class="feature-name">Hit-papers</span>
		<h4>Some papers don't just get cited — they reshape a field.</h4>
		<p>Rankless flags a scholar's highest-impact works and shows where that influence landed.</p>
		<p class="thin">
			Follow a paper's citations year by year, or split them across the fields and topics that
			picked it up - and align trajectories
		</p>
		<div class="mock" aria-hidden="true">
			<div class="seg">
				<span class="on">citation timeline</span><span>citation breakdown</span>
			</div>
			<div class="checks">
				<span class="chk"><i></i>align trajectories</span><span class="chk"><i></i>log scale</span>
			</div>
			<div class="dd">sort: publication year <span class="caret">▾</span></div>
		</div>
		<a class="card-cta" href="{profile}#works">See an author's hit papers →</a>
	</div>

	<div class="card">
		<span class="feature-name">All Works</span>
		<h4>Every paper, ready to cite and export.</h4>
		<p>
			Browse a scholar's full body of work, sort by year or citations, and pull clean references in
			the style you need.
		</p>
		{#if samplePaper}
			<ShowcaseExport data={samplePaper} />
		{/if}
		<a class="card-cta" href="{profile}#works">Browse &amp; export →</a>
	</div>
</div>

<div class="feature-grid">
	<div class="card">
		<span class="feature-name">Peers</span>
		<h4>How does a scholar stack up against their field?</h4>
		<p>
			See how a scholar's citations break down by field and grow over time — measured against
			comparable peers, never flattened into a single rank.
		</p>
		<ShowcasePeers data={peers} />
		<a class="card-cta" href="{profile}#peers">Compare peers →</a>
	</div>

	<div class="card">
		<span class="feature-name">Co-authors</span>
		<h4>Research is a team sport.</h4>
		<p>
			The scholars most often cited alongside an author, linked wherever they've published together
			— click into the network to read the papers behind each connection.
		</p>
		<ShowcaseCoauthors data={coauthors} />
		<a class="card-cta" href="{profile}#network">Explore the network →</a>
	</div>
</div>

<div class="card wide more">
	<span class="feature-name">And more</span>
	<div class="more-grid">
		<div class="more-item">
			<h4>Smarter search</h4>
			<p>
				Faster, typo-tolerant search with a dedicated results page and browser search-bar support.
			</p>
		</div>
		<div class="more-item">
			<h4>Co-author timeline</h4>
			<p>
				Every collaborator placed by the years they published together — not just the closest few.
			</p>
		</div>
		<div class="more-item">
			<h4>Shared papers</h4>
			<p>Click any co-author or connecting line to read the exact papers behind the link.</p>
		</div>
		<div class="more-item">
			<h4>Standing badges</h4>
			<p>Top 5% to top 0.01% — see exactly where an entity stands in each of its fields.</p>
		</div>
	</div>
</div>

<style>
	.feature-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 20px;
		margin-top: 20px;
	}

	.card {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 22px 24px;
		background: var(--text-bg);
		border: 1px solid rgba(var(--color-range-30), 0.18);
		box-shadow: 0 10px 30px rgba(0, 0, 0, 0.06);
		transition:
			transform 0.2s ease,
			box-shadow 0.2s ease;
	}

	.card:hover {
		transform: translateY(-3px);
		box-shadow: 0 16px 44px rgba(0, 0, 0, 0.12);
	}

	.card.wide {
		margin-top: 20px;
	}

	.feature-name {
		font-size: var(--text-xl);
		font-weight: 700;
		color: var(--badge-prestigious-text);
		letter-spacing: -0.01em;
	}

	.card h4 {
		margin: 4px 0 0;
		font-size: var(--text-md);
		font-weight: 700;
		line-height: var(--lh-heading);
		text-align: left;
	}

	.card p {
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--lh-body);
		opacity: 0.82;
		text-align: left;
	}

	.card p.thin {
		opacity: 0.62;
	}

	.login-cols {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 8px 32px;
	}

	.login-cols h4 {
		margin-top: 0;
	}

	.more {
		margin-top: 20px;
	}

	.more-grid {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 14px 32px;
		margin-top: 4px;
	}

	.more-item h4 {
		margin: 0 0 4px;
		font-size: var(--text-base);
		font-weight: 700;
		text-align: left;
	}

	.more-item p {
		margin: 0;
	}

	.card-cta {
		margin-top: auto;
		padding-top: 4px;
		font-size: var(--text-sm);
		font-weight: 700;
		color: var(--badge-prestigious-text);
		width: fit-content;
	}

	.card-cta:hover {
		text-shadow: none;
		text-decoration: underline;
	}

	/* Hit-papers control mock-up: a non-interactive snapshot of the real control bar. */
	.mock {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin: 4px 0 2px;
		font-size: var(--text-xs);
		opacity: 0.9;
	}

	.seg {
		display: inline-flex;
		width: fit-content;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		border-radius: var(--control-bar-pill-radius);
		overflow: hidden;
	}

	.seg span {
		padding: var(--control-bar-pill-pad);
		opacity: 0.5;
	}

	.seg span.on {
		background: rgba(var(--color-range-15), 0.1);
		opacity: 1;
	}

	.checks {
		display: flex;
		gap: 18px;
	}

	.chk {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		opacity: 0.75;
	}

	.chk i {
		width: 12px;
		height: 12px;
		border: 1px solid rgba(var(--color-range-15), 0.35);
		border-radius: 2px;
	}

	.dd {
		width: fit-content;
		padding: 3px 10px;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		border-radius: 4px;
		opacity: 0.75;
	}

	.caret {
		opacity: 0.6;
	}

	@media (max-width: 1000px) {
		.feature-grid {
			grid-template-columns: 1fr;
		}
		.login-cols {
			grid-template-columns: 1fr;
		}
		.more-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}

	@media (max-width: 540px) {
		.more-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
