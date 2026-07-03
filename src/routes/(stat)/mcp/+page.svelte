<script lang="ts">
	import manifestJson from '$lib/assets/data/mcp-manifest.json';
	import type { McpManifest } from '$lib/types/mcp';
	import type { ActionData, PageData } from './$types';

	export let data: PageData;
	export let form: ActionData;

	const m = manifestJson as unknown as McpManifest;
	$: sessions = data.sessions;
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
		<h2>Exploration sessions</h2>
		<p class="note">
			Each session's command, metadata, and verified outputs. Every number was re-issued from the
			backend, not written by the model.
		</p>

		{#if data.isAdmin}
			{#if form?.message}<p class="msg err">{form.message}</p>{/if}
			{#if form?.created}<p class="msg">
					Queued <code>{form.created}</code> — the worker will run it.
				</p>{/if}
			<details class="new">
				<summary>New exploration</summary>
				<form method="POST" action="?/create">
					<div class="row">
						<label
							>Backend
							<select name="backend">
								<option value="live">live</option>
								<option value="local">local</option>
							</select>
						</label>
						<label
							>Visibility
							<select name="visibility">
								<option value="private">private</option>
								<option value="public">public</option>
							</select>
						</label>
						<span class="foci"
							>Foci
							<label><input type="checkbox" name="foci" value="share" checked /> share</label>
							<label><input type="checkbox" name="foci" value="query" /> query</label>
							<label><input type="checkbox" name="foci" value="data-issue" /> data-issue</label>
						</span>
					</div>
					<div class="row">
						<label class="grow"
							>Subject <input
								name="subject"
								placeholder="e.g. Hungary or authors:balazs-lengyel"
							/></label
						>
						<label class="grow">Model <input name="model" placeholder="claude-sonnet-5" /></label>
					</div>
					<div class="row">
						<label class="grow"
							>Question <input name="question" placeholder="a specific investigation" /></label
						>
						<label class="grow"
							>Investigate <input name="investigate" placeholder="<run>[:<id>]" /></label
						>
					</div>
					<button type="submit">Queue run</button>
				</form>
			</details>
		{/if}

		{#if sessions.length === 0}
			<p class="empty">No public sessions yet.</p>
		{:else}
			<ul class="grid">
				{#each sessions as s, i (i)}
					<li class="card">
						<h3><a href="/mcp/runs/{s.name}">{s.title ?? s.name}</a></h3>
						{#if s.meta}
							<p class="meta">
								{s.meta.backend} · {s.meta.model} · foci {s.meta.foci.join(', ')}
							</p>
							<p class="stats">
								{s.meta.counts.findings} findings ·
								{s.meta.counts.metricsReproduced}/{s.meta.counts.metrics} numbers reproduced
							</p>
						{/if}
						<p class="date">{s.meta?.generated ?? s.createdAt.slice(0, 10)}</p>
						{#if data.isAdmin}
							<div class="controls">
								<span class="status {s.status}">{s.status}</span>
								<form method="POST" action="?/visibility">
									<input type="hidden" name="name" value={s.name} />
									<input
										type="hidden"
										name="visibility"
										value={s.visibility === 'public' ? 'private' : 'public'}
									/>
									<button type="submit" class="link">{s.visibility} ⇄</button>
								</form>
								<form
									method="POST"
									action="?/delete"
									on:submit={(e) => {
										if (!confirm('Delete ' + s.name + '?')) e.preventDefault();
									}}
								>
									<input type="hidden" name="name" value={s.name} />
									<button type="submit" class="link danger">delete</button>
								</form>
							</div>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</section>

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
			Each tool proxies one backend endpoint and returns <code>rankless_url</code> backlinks; ids must
			come from the resolution tools, never guessed.
		</p>
		<ul class="cards">
			{#each m.tools as tool, i (i)}
				<li>
					<div class="card-head">
						<code class="name">{tool.name}</code>
						<code class="ep">{tool.endpoint}</code>
					</div>
					<p>{tool.summary}</p>
				</li>
			{/each}
		</ul>
	</section>

	<section>
		<h2>Exploration foci</h2>
		<p class="note">
			A session is scoped to any of these; the agent separates its findings accordingly.
		</p>
		<dl>
			{#each m.foci as focus, i (i)}
				<dt>{focus.name}</dt>
				<dd>{focus.description}</dd>
			{/each}
		</dl>
	</section>

	<section>
		<h2>Scoping a session</h2>
		<dl class="opts">
			{#each m.options as opt, i (i)}
				<dt><code>{opt.flag}</code></dt>
				<dd>{opt.help}</dd>
			{/each}
		</dl>
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
	.empty {
		color: var(--color-text-light);
	}
	.grid {
		list-style: none;
		padding: 0;
		display: grid;
		gap: 0.8rem;
		grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr));
	}
	.card {
		border: 1px solid var(--color-theme-lightgrey);
		border-radius: 8px;
		padding: 0.9rem 1rem;
	}
	.card:hover {
		border-color: rgba(var(--color-range-30), 0.6);
	}
	.card h3 {
		font-size: var(--text-md);
		margin: 0 0 0.4em;
	}
	.card h3 a {
		color: var(--accent-text);
		text-decoration: none;
	}
	.meta,
	.stats,
	.date {
		margin: 0.2em 0;
		font-size: var(--text-xs);
		color: var(--color-text-light);
	}
	.stats {
		color: var(--color-text);
	}
	.controls {
		display: flex;
		gap: 0.8rem;
		align-items: center;
		margin: 0.5em 0 0;
	}
	.controls form {
		margin: 0;
	}
	.status {
		font-size: var(--text-xs);
		padding: 0.1em 0.5em;
		border-radius: 8px;
		background: rgba(var(--color-range-30), 0.12);
	}
	.status.done {
		background: rgba(var(--color-range-15), 0.2);
	}
	.status.failed {
		background: var(--color-theme-red);
	}
	.link {
		background: none;
		border: none;
		padding: 0;
		color: var(--accent-text);
		cursor: pointer;
		font-family: var(--font-mono);
		font-size: var(--text-xs);
	}
	.danger {
		color: var(--color-graph-pink);
	}
	.msg {
		padding: 0.5em 0.8em;
		border-radius: 4px;
		background: rgba(var(--color-range-30), 0.1);
		font-size: var(--text-sm);
	}
	.msg.err {
		color: var(--color-graph-pink);
	}
	.new {
		margin: 0.8rem 0 1.2rem;
		border: 1px solid var(--color-theme-lightgrey);
		border-radius: 8px;
		padding: 0.6rem 1rem;
	}
	.new summary {
		cursor: pointer;
		font-weight: bold;
		font-size: var(--text-sm);
	}
	.new form {
		display: grid;
		gap: 0.7rem;
		max-width: 44rem;
		margin-top: 0.8rem;
	}
	.row {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
		align-items: end;
	}
	.new label {
		display: grid;
		gap: 0.2rem;
		font-size: var(--text-sm);
	}
	.grow {
		flex: 1 1 18rem;
	}
	input,
	select {
		font-family: var(--font-mono);
		padding: 0.3em 0.4em;
	}
	.foci {
		font-size: var(--text-sm);
		display: flex;
		gap: 0.8rem;
		align-items: center;
	}
	.foci label {
		display: inline-flex;
		flex-direction: row;
		gap: 0.25rem;
		align-items: center;
	}
	button[type='submit'] {
		justify-self: start;
		padding: 0.4em 1em;
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
	.opts dt code {
		color: var(--accent-text);
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
