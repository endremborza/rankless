<script lang="ts">
	import type { SurveySubmit } from '$lib/types';

	function getRatables() {
		let ratables = [
			{
				title: 'Curate your own profile data as a logged-in user',
				desc: 'correct publication lists, merge duplicate profiles, or flag inaccuracies',
				score: 5,
				id: 'login'
			},
			{
				title: 'Compare institutions or authors side-by-side',
				desc: 'see differences in impact, focus, and collaboration patterns',
				score: 5,
				id: 'compare'
			},
			{
				title: 'Generate lists of publications or citations to drop into reports',
				desc: 'formatted outputs for grant applications, annual reviews, or CV updates',
				score: 5,
				id: 'publist'
			},
			{
				title: 'Discover relevant scholars or fields based on your interests',
				desc: 'find potential collaborators, interesting papers or areas worth further exploration',
				score: 5,
				id: 'discover'
			}
		];
		shuffle(ratables);
		return ratables;
	}

	let ratables = getRatables();

	let q1Options = [
		'researcher',
		'administrator',
		'student',
		'journalist',
		'policy analyst',
		'industry professional',
		'other'
	];

	let question1 = 0;
	let otherRole = '';
	let customOption = '';
	let submitting = false;
	let success = false;
	let errorMsg: string | null = null;

	function shuffle<T>(array: T[]) {
		let currentIndex = array.length;
		while (currentIndex !== 0) {
			let randomIndex = Math.floor(Math.random() * currentIndex);
			currentIndex--;
			[array[currentIndex], array[randomIndex]] = [array[randomIndex], array[currentIndex]];
		}
	}

	async function submitForm(e: Event) {
		e.preventDefault();
		submitting = true;
		errorMsg = null;

		const scores = ratables.map(({ id, score }) => {
			return { id, score };
		});

		const payload: SurveySubmit = {
			role: q1Options[question1],
			customRole: otherRole,
			scores,
			customOption: customOption || undefined,
			timestamp: new Date().toISOString()
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
			<p class="intro">Your feedback helps us decide what to build next.</p>

			<form on:submit|preventDefault={submitForm} class="form">
				<!-- ROLE SELECTION -->
				<fieldset class="block">
					<legend>What best describes your role?</legend>

					<div class="radio-list">
						{#each q1Options as option, i (i)}
							<label class="radio-item">
								<input type="radio" bind:group={question1} value={i} required />
								<span>{option}</span>
							</label>
						{/each}
					</div>
				</fieldset>
				{#if question1 == q1Options.length - 1}
					<div class="block">
						<label for="custom">Specifically</label>
						<input
							id="custom"
							type="text"
							bind:value={otherRole}
							placeholder="Your role"
							class="text-input"
						/>
					</div>
				{/if}

				<div class="block">
					<h3 class="block-title">Rate these potential features (1–10)</h3>

					<div class="score-list">
						{#each ratables as { title, desc, score, id }, __i (__i)}
							<div class="score-row">
								<div class="score-info">
									<label for={id} class="score-title">{title}</label>
									<p class="score-desc">{desc}</p>
								</div>

								<div class="score-input">
									<input {id} type="range" min="1" max="10" bind:value={score} />
									<span class="score-value">{score}</span>
								</div>
							</div>
						{/each}
					</div>
				</div>

				<div class="block">
					<label for="custom">Other (optional)</label>
					<input
						id="custom"
						type="text"
						bind:value={customOption}
						placeholder="Your idea..."
						class="text-input"
					/>
				</div>

				<!-- ACTIONS -->
				<div class="actions">
					<button type="submit" class="btn primary" disabled={submitting}>
						{#if submitting}Submitting…{/if}
						{#if !submitting}Submit{/if}
					</button>
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
		padding: 2rem;
	}

	h1 {
		margin-bottom: 0.25rem;
	}

	.intro {
		margin-bottom: 1.5rem;
	}

	.block {
		margin-bottom: 2rem;
	}

	/* Fieldset / legend */
	fieldset {
		border: none;
		padding: 0;
	}

	legend {
		font-weight: 600;
		margin-bottom: 0.75rem;
	}

	.radio-list {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.radio-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.35rem 0;
		cursor: pointer;
	}

	/* SCORES */
	.block-title {
		margin-bottom: 0.75rem;
	}

	.score-list {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.score-row {
		display: grid;
		grid-template-columns: 1fr auto;
		align-items: center;
		gap: 1rem;
		padding: 0.75rem 0;
		border-bottom: 1px solid var(--border-light);
	}

	.score-info {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	.score-title {
		font-weight: 600;
		font-size: var(--text-lg);
	}

	.score-desc {
		font-size: var(--text-sm);
		margin: 0;
	}

	.score-input {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	input[type='range'] {
		width: 120px;
	}

	.score-value {
		width: 28px;
		text-align: center;
		font-weight: 600;
	}

	/* TEXT INPUT */
	.text-input {
		margin-top: 0.5rem;
		width: 100%;
		padding: 0.6rem;
		border: 1px solid var(--border-light);
	}

	/* ACTIONS */
	.actions {
		display: flex;
		justify-content: center;
		margin-top: 1rem;
	}

	.error {
		color: var(--color-err);
		margin-top: 1rem;
		text-align: center;
	}
</style>
