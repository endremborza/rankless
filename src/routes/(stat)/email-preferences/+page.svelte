<script lang="ts">
	import { EMAIL_PURPOSES } from '$lib/types/email-consent';
	import type { EmailPurposeKey } from '$lib/types/email-consent';
	import type { PageData } from './$types';

	export let data: PageData;

	let email = data.consent?.email ?? data.prefillEmail;
	let selected = new Set<EmailPurposeKey>(data.consent?.purposes ?? []);
	let hasConsent = data.consent !== null;
	let status: '' | 'saving' | 'saved' | 'withdrawn' = '';
	let errorMsg = '';

	function toggle(key: EmailPurposeKey) {
		const next = new Set(selected);
		if (next.has(key)) next.delete(key);
		else next.add(key);
		selected = next;
	}

	async function save() {
		errorMsg = '';
		if (selected.size === 0) {
			errorMsg = 'Pick at least one kind of email, or withdraw below.';
			return;
		}
		status = 'saving';
		const res = await fetch('/api/email-consent', {
			method: 'POST',
			headers: { 'content-type': 'application/json' },
			body: JSON.stringify({ email, purposes: [...selected] })
		});
		if (res.ok) {
			status = 'saved';
			hasConsent = true;
		} else {
			const body = await res.json().catch(() => ({}));
			errorMsg = body.error ?? `Could not save (${res.status}).`;
			status = '';
		}
	}

	async function withdraw() {
		errorMsg = '';
		status = 'saving';
		const res = await fetch('/api/email-consent', { method: 'DELETE' });
		if (res.ok) {
			status = 'withdrawn';
			hasConsent = false;
			selected = new Set();
		} else {
			errorMsg = `Could not withdraw (${res.status}).`;
			status = '';
		}
	}
</script>

<svelte:head>
	<title>Email preferences — Rankless</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<section>
	<div class="prose">
		<h1>Email preferences</h1>
		<p>
			Rankless never emails you unless you ask it to. Tell us where to reach you and what you'd like
			to hear about — you can change or withdraw this at any time. See the
			<a href="/privacy">privacy notice</a> for how we handle your address.
		</p>

		<label class="field" for="email-input">Email address</label>
		<input
			id="email-input"
			type="email"
			autocomplete="email"
			placeholder="you@example.org"
			bind:value={email}
			on:input={() => (status = '')}
		/>

		<fieldset>
			<legend>Email me about</legend>
			{#each EMAIL_PURPOSES as p, i (i)}
				<label class="purpose">
					<input type="checkbox" checked={selected.has(p.key)} on:change={() => toggle(p.key)} />
					<span>
						<strong>{p.label}</strong>
						<span class="blurb">{p.blurb}</span>
					</span>
				</label>
			{/each}
		</fieldset>

		{#if errorMsg}<p class="err">{errorMsg}</p>{/if}
		{#if status === 'saved'}<p class="ok">
				Saved — thank you. We'll only email you about what you picked.
			</p>{/if}
		{#if status === 'withdrawn'}<p class="ok">
				Withdrawn — your address has been removed from the active mailing list.
			</p>{/if}

		<div class="actions">
			<button class="primary" disabled={status === 'saving'} on:click={save}>
				{hasConsent ? 'Update preferences' : 'Save preferences'}
			</button>
			{#if hasConsent}
				<button class="link" disabled={status === 'saving'} on:click={withdraw}>
					Withdraw consent
				</button>
			{/if}
		</div>
	</div>
</section>

<style>
	section {
		padding: 56px 0;
	}

	.prose {
		max-width: 640px;
		margin: 0 auto;
		padding: 0 var(--unified-margin, 16px);
		line-height: var(--lh-body);
	}

	.prose h1 {
		font-size: 2.2rem;
		margin: 0 0 12px 0;
		letter-spacing: -0.01em;
	}

	.field {
		display: block;
		font-weight: bold;
		margin: 24px 0 6px 0;
	}

	input[type='email'] {
		width: 100%;
		box-sizing: border-box;
		font: inherit;
		padding: 8px 10px;
		border: 1px solid var(--color-theme-darkgrey);
		border-radius: 3px;
	}

	fieldset {
		margin: 28px 0 0 0;
		padding: 0;
		border: none;
	}

	legend {
		font-weight: bold;
		padding: 0;
		margin-bottom: 8px;
	}

	.purpose {
		display: flex;
		gap: 10px;
		align-items: flex-start;
		padding: 8px 0;
		cursor: pointer;
	}

	.purpose input {
		margin-top: 4px;
		flex-shrink: 0;
	}

	.purpose .blurb {
		display: block;
		font-size: var(--text-sm);
		opacity: 0.75;
	}

	.actions {
		display: flex;
		align-items: center;
		gap: 16px;
		margin-top: 28px;
	}

	button {
		font: inherit;
		cursor: pointer;
	}

	button:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.primary {
		background: var(--color-theme-darkblue);
		color: var(--color-theme-white);
		border: none;
		padding: 9px 18px;
		border-radius: 3px;
	}

	.link {
		background: none;
		border: none;
		color: var(--color-err);
		text-decoration: underline;
		padding: 0;
	}

	.err {
		color: var(--color-err);
	}

	.ok {
		color: var(--color-ok);
	}
</style>
