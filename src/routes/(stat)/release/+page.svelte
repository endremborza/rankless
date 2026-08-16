<script lang="ts">
	import reportRaw from '$lib/assets/data/release-report.json';
	import type { ReleaseReport, ReleaseSnapshot } from '$lib/types/release-report';
	import { APP_NAME } from '$lib/constants';

	// Baked by pyscripts/release_report.py from the release record (docs/deploy.md).
	const report = reportRaw as unknown as ReleaseReport;

	const ENTITY_NAMES: Record<string, string> = {
		works: 'Works',
		authors: 'Scholars',
		sources: 'Journals',
		institutions: 'Institutions'
	};

	const KIND_NAMES: Record<string, string> = {
		disown_paper: 'papers removed from a scholar profile',
		merge_papers: 'duplicate papers merged',
		merge_authors: 'duplicate scholar records merged',
		claim_paper: 'papers claimed by their author'
	};

	const fmt = (n: number) => n.toLocaleString('en-US');
	const fmtChange = (n: number) => (n > 0 ? '+' : '') + fmt(n);
	const prettify = (k: string) => k.replace(/_/g, ' ');
	const plural = (n: number) => (n === 1 ? '' : 's');
	const dateOf = (run_id: string) => run_id.slice(0, 10);
	const snapshotOf = (snap: ReleaseSnapshot) => snap.date ?? snap.name;

	const entityName = (key: string) => ENTITY_NAMES[key] ?? key;
	const entityRows = Object.entries(report.entities);
	const deltaRows = Object.entries(report.deltas?.entities ?? {});

	const claimed = (report.restored?.claim_auto ?? 0) + (report.restored?.claim_merged ?? 0);
	const claimedClause = claimed > 0 ? `, ${fmt(claimed)} of them individually claimed` : '';
</script>

<svelte:head>
	<title>Data release — {APP_NAME}</title>
	<meta
		name="description"
		content="What the current Rankless data release contains: the OpenAlex snapshot it was built from, the filtering it went through, and the user corrections built into it."
	/>
</svelte:head>

<section>
	<div class="prose">
		<h1>Data release</h1>
		<p class="subtitle">
			Every Rankless deployment serves exactly one documented data release. This report is
			regenerated from that release's build record — it describes the data you are browsing right
			now.
		</p>
		<p class="updated">
			Release of {dateOf(report.run_id)}, built from OpenAlex snapshot {snapshotOf(
				report.snapshot
			)}.
		</p>

		<h2>Filtering</h2>
		<p>
			Starting from the full OpenAlex snapshot, each entity type passes a series of mechanical
			screens before it is served:
		</p>
		{#each entityRows as [key, chain], __i (__i)}
			<div class="funnel">
				<div class="funnel-head">
					<h3>{entityName(key)}</h3>
					<span class="final"><strong>{fmt(chain.final)}</strong> served</span>
				</div>
				<ol>
					{#each chain.steps as step, __j (__j)}
						<li><span class="count">{fmt(step.kept)}</span> {step.label}</li>
					{/each}
				</ol>
			</div>
		{/each}

		<h2>User corrections</h2>
		{#if report.ledger.applied_total > 0}
			<p>
				Scholars who signed in with their ORCID iD have corrected their own records; every such edit
				lands in a public, revocable ledger. This release integrates
				<strong>{fmt(report.ledger.applied_total)}</strong>
				correction{plural(report.ledger.applied_total)}:
			</p>
			<ul>
				{#each Object.entries(report.ledger.applied) as [kind, n], __i (__i)}
					<li><span class="count">{fmt(n)}</span> {KIND_NAMES[kind] ?? prettify(kind)}</li>
				{/each}
			</ul>
		{:else}
			<p>No user corrections were pending for this release.</p>
		{/if}
		{#if report.ledger.skipped_total > 0}
			<p>
				{fmt(report.ledger.skipped_total)} recorded correction{plural(report.ledger.skipped_total)} could
				not be integrated yet:
			</p>
			<ul>
				{#each Object.entries(report.ledger.skipped) as [reason, n], __i (__i)}
					<li><span class="count">{fmt(n)}</span> {prettify(reason)}</li>
				{/each}
			</ul>
		{:else if report.ledger.applied_total > 0}
			<p>No recorded correction was left out.</p>
		{/if}

		{#if report.restored && report.restored.outside_standard > 0}
			<h2>Papers restored by their authors</h2>
			<p>
				Signed-in scholars keep their full body of work in the dataset: every work of a registered
				owner rides through the mechanical screens above. This release serves
				<strong>{fmt(report.restored.outside_standard)}</strong>
				paper{plural(report.restored.outside_standard)} — from
				<strong>{fmt(report.restored.cohort)}</strong>
				signed-in researcher{plural(report.restored.cohort)} — that the standard screens alone would have
				dropped{claimedClause}.
			</p>
		{/if}

		{#if report.claims && report.claims.submitted > 0}
			<h2>Paper claims</h2>
			<p>
				<strong>{fmt(report.claims.applied)}</strong>
				of {fmt(report.claims.submitted)} submitted paper claims are resolved in this release.
			</p>
			{#if Object.keys(report.claims.unresolved_by_cause).length > 0}
				<p>The rest could not be:</p>
				<ul>
					{#each Object.entries(report.claims.unresolved_by_cause) as [cause, n], __i (__i)}
						<li><span class="count">{fmt(n)}</span> {prettify(cause)}</li>
					{/each}
				</ul>
			{/if}
		{/if}

		<h2>Changes since the previous release</h2>
		{#if report.deltas && report.previous}
			<p>
				Compared to the release of {dateOf(report.previous.run_id)} (snapshot
				{snapshotOf(report.previous.snapshot)}):
			</p>
			<ul>
				{#each deltaRows as [key, d], __i (__i)}
					<li>
						<span class="count">{fmtChange(d.change)}</span>
						{entityName(key).toLowerCase()} ({fmt(d.previous)} → {fmt(d.current)})
					</li>
				{/each}
				<li>
					<span class="count">{fmtChange(report.deltas.applied_total.new)}</span> newly integrated
					correction{plural(report.deltas.applied_total.new)}
					({fmt(report.deltas.applied_total.current)} in total)
				</li>
			</ul>
		{:else}
			<p>
				This is the first release documented with a build record — from the next release on, this
				section shows what changed.
			</p>
		{/if}

		<h2>Provenance</h2>
		<p>
			Release <code>{report.run_id}</code> was built from
			<code>{report.snapshot.name}</code> at commit <code>{report.git_commit}</code>; the serving
			backend echoes the release stamp <code>{report.stamp}</code>, which is verified before every
			deployment goes live.
		</p>
	</div>
</section>

<style>
	section {
		display: flex;
		justify-content: center;
		padding: 32px var(--unified-margin) 64px;
	}
	.prose {
		max-width: 780px;
		width: 100%;
	}
	h1 {
		margin-bottom: 4px;
	}
	.subtitle {
		font-size: var(--text-lg);
		opacity: 0.85;
	}
	.updated {
		opacity: 0.6;
		font-size: var(--text-sm);
		margin-bottom: 28px;
	}
	h2 {
		margin: 36px 0 10px;
	}
	.funnel {
		border: 1px solid rgba(var(--color-range-30), 0.25);
		padding: 14px 18px;
		margin: 14px 0;
	}
	.funnel-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 12px;
		flex-wrap: wrap;
	}
	.funnel-head h3 {
		margin: 0;
	}
	.final {
		color: var(--highlight-text);
	}
	ol {
		margin: 10px 0 0;
		padding-left: 0;
		list-style: none;
	}
	ol li + li::before {
		content: '→ ';
		opacity: 0.6;
	}
	li {
		margin: 4px 0;
	}
	.count {
		font-variant-numeric: tabular-nums;
		font-weight: 700;
	}
	code {
		font-size: 0.9em;
		background: rgba(var(--color-range-30), 0.12);
		padding: 1px 5px;
		border-radius: 3px;
		word-break: break-all;
	}
</style>
