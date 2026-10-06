<script lang="ts">
	import manifestJson from '$lib/assets/data/mcp-manifest.json';
	import type { McpManifest } from '$lib/types/mcp';

	const m = manifestJson as unknown as McpManifest;
</script>

<svelte:head>
	<title>MCP & agentic exploration — Rankless</title>
	<meta
		name="description"
		content="Rankless exposes its citation backend over the Model Context Protocol, and mines verified, reproducible stories from it with an LLM agent."
	/>
</svelte:head>

<article class="mcp">
	<header>
		<h1>MCP &amp; agentic exploration</h1>
		<p class="lede">
			Rankless wraps its low-latency citation backend in the
			<a href="https://modelcontextprotocol.io">Model Context Protocol</a>, so any MCP client can
			explore the data. On top of it, an LLM agent mines interesting stories — and every number it
			publishes is <strong>re-issued from the backend</strong>, never taken from the model.
		</p>
	</header>

	<section>
		<h2>Connect your agent</h2>
		<p class="note">
			Point any MCP client at the hosted endpoint (<code>{m.connect.transport}</code>):
		</p>
		<div class="cmds">
			{#each m.connect.snippets as sn, i (i)}
				<div class="cmd">
					<span>{sn.label}</span>
					<pre><code>{sn.cmd}</code></pre>
				</div>
			{/each}
		</div>
	</section>

	<section>
		<h2>Tools</h2>
		<p class="note">
			Each data tool proxies one backend endpoint and returns <code>rankless_url</code> backlinks;
			ids must come from the resolution tools, never guessed. Every data-tool response carries a
			receipt naming the call that produced it; <code>verify_claims</code> re-issues cited numbers
			and
			<code>suggest_endpoint</code> records what the tools lacked.
		</p>
		<ul class="cards">
			{#each m.tools as tool, i (i)}
				<li>
					<div class="card-head">
						<code class="name">{tool.name}</code>
						{#if tool.endpoint}<code class="ep">{tool.endpoint}</code>{/if}
					</div>
					<p>{tool.summary}</p>
				</li>
			{/each}
		</ul>
	</section>

	<section>
		<h2>Resources &amp; prompts</h2>
		<dl>
			{#each m.resources as r, i (i)}
				<dt><code>{r.uri}</code></dt>
				<dd>{r.text.split('\n')[0]}</dd>
			{/each}
			{#each m.prompts as p, i (i)}
				<dt><code>{p.name}</code> <span class="kind">prompt</span></dt>
				<dd>{p.description.split('\n')[0]}</dd>
			{/each}
		</dl>
	</section>

	<footer class="genline">Generated {m.generated} from the live tool definitions.</footer>
</article>

<style>
	.mcp {
		max-width: 52rem;
		margin: 0 auto;
		padding: var(--unified-padding);
		line-height: var(--lh-body);
	}
	h1 {
		font-size: var(--text-2xl);
		margin-bottom: 0.3em;
	}
	.lede {
		font-size: var(--text-md);
		color: var(--color-text);
	}
	section {
		margin-top: 2.5rem;
	}
	h2 {
		font-size: var(--text-xl);
		border-bottom: 2px solid rgba(var(--color-range-30), 0.35);
		padding-bottom: 0.2em;
	}
	.note {
		color: var(--color-text-light);
		font-size: var(--text-sm);
	}
	code {
		font-family: var(--font-mono);
	}
	.cards {
		list-style: none;
		padding: 0;
		display: grid;
		gap: 0.6rem;
		grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
	}
	.cards li {
		border: 1px solid var(--color-theme-lightgrey);
		border-radius: 6px;
		padding: 0.6rem 0.8rem;
	}
	.card-head {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 0.3rem;
		align-items: baseline;
	}
	.card-head .name {
		color: var(--accent-text);
		font-weight: bold;
	}
	.card-head .ep {
		font-size: var(--text-xs);
		color: var(--color-text-light);
	}
	.cards p {
		margin: 0.4em 0 0;
		font-size: var(--text-sm);
	}
	dl {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.4rem 1rem;
	}
	dt {
		font-weight: bold;
		color: var(--accent-text);
	}
	dd {
		margin: 0;
		font-size: var(--text-sm);
	}
	.cmds {
		margin-top: 1rem;
		display: grid;
		gap: 0.5rem;
	}
	.cmd {
		display: grid;
		gap: 0.15rem;
	}
	.cmd span {
		font-size: var(--text-xs);
		color: var(--color-text-light);
	}
	.cmd pre {
		margin: 0;
		background: rgba(var(--color-range-30), 0.08);
		padding: 0.5em 0.7em;
		border-radius: 4px;
		overflow-x: auto;
	}
	.cmd pre code {
		background: none;
		padding: 0;
	}
	.kind {
		font-size: var(--text-2xs);
		color: var(--color-text-light);
	}
	.genline {
		margin-top: 3rem;
		font-size: var(--text-xs);
		color: var(--color-text-light);
	}
</style>
