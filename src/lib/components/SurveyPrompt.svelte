<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	let visible = true;
	let dismissing = false;

	function openSurvey() {
		goto('/survey');
	}

	async function rejectSurvey() {
		dismissing = true;
		await fetch('/api/survey/reject', { method: 'POST' });
		visible = false;
	}

	function closeNow() {
		rejectSurvey();
	}
</script>

{#if visible}
	<div class="survey-overlay" role="dialog" aria-modal="false">
		<div class="survey-container shadowy padded">
			<div class="survey-left">
				<strong>Help improve the site</strong>
				<p class="muted">Quick 30-second survey — we'd appreciate your feedback.</p>
			</div>
			<div class="survey-actions">
				<button class="btn primary" on:click={openSurvey} disabled={dismissing}>Take survey</button>
				<button class="btn close" aria-label="Close" on:click={closeNow}>&times;</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.survey-overlay {
		position: fixed;
		bottom: 1rem;
		left: 1rem;
		right: 1rem;
		z-index: 1200;
		display: flex;
		justify-content: center;
		pointer-events: auto;
	}

	.survey-container {
		width: min(1100px, calc(100% - 2rem));
		backgroundx: linear-gradient(180deg, var(--text-bg), var(--text-bg-3));
		background: var(--text-bg-2);
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.survey-left {
		flex: 1;
	}
	.survey-left strong {
		display: block;
		font-size: var(--text-md);
	}
	.muted {
		color: var(--accent-text);
		margin: 0.25rem 0 0;
	}

	.survey-actions {
		display: flex;
		gap: 8px;
		align-items: center;
	}

	.btn.close {
		font-size: var(--text-xl);
		line-height: 1;
		background: transparent;
		padding: 0.25rem 0.5rem;
	}
</style>
