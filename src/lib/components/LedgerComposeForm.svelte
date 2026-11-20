<script lang="ts">
	import {
		draftBody,
		type ComposeDraft,
		type EventBody,
		type WriteOutcome
	} from '$lib/utils/ledger-client';
	import { COMPOSE_COPY } from '$lib/utils/ledger-display';

	export let draft: ComposeDraft;
	export let ownSemanticId: string;
	export let submitLabel: string;
	export let doneText: string;
	export let submit: (body: EventBody) => Promise<WriteOutcome>;
	export let cancel: (() => void) | null = null;

	const OUTCOME_TEXT: Record<WriteOutcome, string> = {
		done: doneText,
		failed: 'Failed',
		unchanged: 'Unchanged: it names the same record'
	};

	let values = { ...draft };
	let status = '';

	$: placeholders = COMPOSE_COPY[values.kind];
	$: body = draftBody(values, ownSemanticId);

	async function onSubmit() {
		if (!body) return;
		status = 'Submitting...';
		const outcome = await submit(body);
		if (outcome === 'done') values = { ...draft };
		status = OUTCOME_TEXT[outcome];
	}
</script>

<form
	class="compose"
	class:stacked={placeholders.note !== null}
	on:submit|preventDefault={onSubmit}
>
	<input
		type="text"
		bind:value={values.identifier}
		placeholder={placeholders.identifier}
		aria-label={placeholders.identifier}
		class="text-input"
	/>
	{#if placeholders.note}
		<textarea
			bind:value={values.note}
			placeholder={placeholders.note}
			aria-label={placeholders.note}
			class="text-input note-input"
			rows="2"
		></textarea>
	{/if}
	<div class="form-row">
		<button type="submit" class="btn-sm confirm" disabled={!body}>{submitLabel}</button>
		{#if cancel}<button type="button" class="btn-sm" on:click={cancel}>Cancel</button>{/if}
		{#if status}<span class="op-status">{status}</span>{/if}
	</div>
</form>

<style>
	.compose,
	.form-row {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.compose.stacked {
		flex-direction: column;
		align-items: stretch;
	}

	.text-input {
		font-size: var(--text-sm);
		padding: 4px 8px;
		border-radius: 3px;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		background: transparent;
		color: var(--color-text);
		font-family: inherit;
		max-width: 400px;
		flex: 1;
	}

	.stacked .text-input {
		flex: none;
	}

	.note-input {
		resize: vertical;
	}

	.op-status {
		font-size: var(--text-xs);
		opacity: 0.5;
	}
</style>
