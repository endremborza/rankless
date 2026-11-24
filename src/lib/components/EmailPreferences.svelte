<script lang="ts">
	import { onMount } from 'svelte';
	import { EMAIL_PURPOSES, isValidEmail } from '$lib/types/email-consent';
	import type { EmailPurposeKey, EmailSettings } from '$lib/types/email-consent';

	let email = '';
	let address = '';
	let purposes = new Set<EmailPurposeKey>();
	let savedPurposes: EmailPurposeKey[] = [];
	let loaded = false;
	let status = '';
	let failed = false;
	let saving = false;
	let unsent = false;

	onMount(async () => {
		try {
			const res = await fetch('/api/email-consent');
			if (!res.ok) return report(`Could not load your email settings (${res.status}).`, true);
			const settings: EmailSettings = await res.json();
			email = address = settings.email;
			purposes = new Set(settings.purposes);
			savedPurposes = settings.purposes;
			loaded = true;
		} catch {
			report('Could not load your email settings.', true);
		}
	});

	function report(text: string, isError: boolean) {
		status = text;
		failed = isError;
	}

	function commitAddress(): boolean {
		const typed = email.trim();
		if (!isValidEmail(typed)) {
			report('Enter a valid email address first.', true);
			return false;
		}
		address = typed;
		return true;
	}

	async function post(settings: EmailSettings): Promise<string | null> {
		try {
			const res = await fetch('/api/email-consent', {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify(settings)
			});
			if (res.ok) return null;
			const body = await res.json().catch(() => ({}));
			return body.error ?? `Could not save (${res.status}).`;
		} catch {
			return 'Could not save: the request failed.';
		}
	}

	// One request at a time: a change made while one is in flight is sent, as the whole current
	// choice, once it returns, so the last change wins; a failure resets the boxes to the saved choice.
	async function save() {
		unsent = true;
		if (saving) return;
		saving = true;
		report('Saving…', false);
		while (unsent) {
			unsent = false;
			const settings = { email: address, purposes: [...purposes] };
			const error = await post(settings);
			if (error === null) {
				savedPurposes = settings.purposes;
				continue;
			}
			purposes = new Set(savedPurposes);
			unsent = false;
			report(error, true);
		}
		saving = false;
		if (!failed) report('Saved', false);
	}

	function toggle(e: Event, key: EmailPurposeKey) {
		const box = e.currentTarget as HTMLInputElement;
		const next = new Set(purposes);
		if (box.checked) next.add(key);
		else next.delete(key);
		if (next.size > 0 && !commitAddress()) {
			box.checked = !box.checked;
			return;
		}
		purposes = next;
		save();
	}

	function addressChanged() {
		if (purposes.size > 0 && commitAddress()) save();
	}
</script>

<fieldset id="email-preferences" class="email-prefs" disabled={!loaded}>
	<legend>Email me about</legend>
	{#each EMAIL_PURPOSES as p, i (i)}
		<label class="purpose">
			<input type="checkbox" checked={purposes.has(p.key)} on:change={(e) => toggle(e, p.key)} />
			{p.label}
		</label>
	{/each}
	<label class="address">
		at
		<input
			type="email"
			autocomplete="email"
			placeholder="you@example.org"
			bind:value={email}
			on:change={addressChanged}
		/>
	</label>
	<p class="foot">
		<span class="status" class:failed aria-live="polite">{status}</span>
		<a href="/privacy">How we handle your address</a>
	</p>
</fieldset>

<style>
	.email-prefs {
		margin: 16px 0 0 0;
		padding: 12px 16px;
		border: 1px solid var(--color-theme-darkgrey);
		border-radius: 3px;
		display: flex;
		flex-direction: column;
		gap: 6px;
		max-width: 480px;
	}

	legend {
		font-weight: bold;
		padding: 0 4px;
	}

	label {
		display: flex;
		align-items: center;
		gap: 8px;
		cursor: pointer;
	}

	.address input {
		flex: 1;
		min-width: 0;
		font: inherit;
		padding: 4px 8px;
		border: 1px solid var(--color-theme-darkgrey);
		border-radius: 3px;
	}

	.foot {
		display: flex;
		justify-content: space-between;
		gap: 12px;
		margin: 2px 0 0 0;
		font-size: var(--text-sm);
	}

	.status {
		color: var(--color-ok);
	}

	.status.failed {
		color: var(--color-err);
	}
</style>
