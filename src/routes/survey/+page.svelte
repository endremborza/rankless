<script lang="ts">
	import type { SurveySubmit } from '$lib/types';
	import { onMount } from 'svelte';

	let ratables = [
		{
			title: 'Curate your own profile data as a logged-in user',
			desc: '(correct publication lists, merge duplicate profiles, or flag inaccuracies)',
			score: 5,
			id: 'login'
		},
		{
			title: 'Compare institutions or authors side-by-side',
			desc: '(see differences in impact, focus, and collaboration patterns)',
			score: 5,
			id: 'compare'
		},
		{
			title: 'Generate lists of publications or citations to drop into reports',
			desc: '(formatted outputs for grant applications, annual reviews, or CV updates)',
			score: 5,
			id: 'publist'
		},
		{
			title: 'Discover relevant scholars or fields based on your interests',
			desc: '(find potential collaborators, interesting papers or areas worth further exploration)',
			score: 5,
			id: 'discover'
		}
	];

	let q1Options = [
		'researcher',
		'administrator',
		'student',
		'journalist',
		'policy analyst',
		'industry professional',
		'other'
	];

	let question1: string = '';
	let scores: number[] = [5, 5, 5, 5];
	let customOption = '';
	let submitting = false;
	let success = false;
	let errorMsg: string | null = null;

	function shuffle(array: any[]) {
		let currentIndex = array.length;
		while (currentIndex != 0) {
			let randomIndex = Math.floor(Math.random() * currentIndex);
			currentIndex--;
			[array[currentIndex], array[randomIndex]] = [array[randomIndex], array[currentIndex]];
		}
	}

	onMount(() => {
		shuffle(ratables);
	});

	async function submitForm(e: Event) {
		e.preventDefault();
		submitting = true;
		errorMsg = null;

		const payload: SurveySubmit = {
			question1,
			scores,
			customOption: customOption || undefined
		};

		const res = await fetch('/api/survey', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(payload)
		});

		if (res.ok) {
			success = true;
		} else {
			errorMsg = await res.text();
		}
		submitting = false;
	}
</script>

<main class="page">
	<section class="card shadowy padded">
		{#if !success}
			<h1>Quick survey</h1>
			<form on:submit|preventDefault={submitForm} class="form">
				<fieldset>
					<legend>What best describes your role?</legend>
					{#each q1Options as option, i}
						<label><input type="radio" bind:group={question1} value={i} required /> {option}</label>
					{/each}
				</fieldset>

				<div class="scores">
					<p>Rate these (1–10)</p>
					{#each ratables as { title, desc, score, id }}
						<div class="score-row">
							<label for={id}>{title}</label>
							<p>{desc}</p>
							<input {id} type="range" min="1" max="10" bind:value={score} />
							<span class="score-value">{score}</span>
						</div>
					{/each}
				</div>

				<div class="custom">
					<label for="custom">Other (optional)</label>
					<input id="custom" type="text" bind:value={customOption} placeholder="Your idea..." />
				</div>

				<div class="actions">
					<button type="submit" class="btn primary" disabled={submitting}>Submit</button>
				</div>

				{#if errorMsg}
					<p class="error">{errorMsg}</p>
				{/if}
			</form>
		{:else}
			<h2>Thanks for your feedback!</h2>
			<p>We recorded your response.</p>
		{/if}
	</section>
</main>

<style>
	.page {
		padding: 2rem;
		display: flex;
		justify-content: center;
	}
	.card {
		width: min(760px, 95%);
		background: var(--text-bg-2);
	}
	fieldset {
		margin-bottom: 1rem;
		border: none;
		display: flex;
		gap: 12px;
		padding: 0;
	}
	.scores {
		margin-bottom: 1rem;
	}
	.score-row {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0.35rem 0;
	}
	.score-value {
		width: 32px;
		text-align: center;
	}
	.custom input {
		width: 100%;
		padding: 0.5rem;
		border-radius: var(--borad);
		border: 1px solid #ddd;
	}
	.actions {
		display: flex;
		gap: 8px;
		margin-top: 1rem;
	}
	.error {
		color: #b00020;
	}
</style>
