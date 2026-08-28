<!-- Full-viewport phone-first frame for the arcade game pages (/game-countries,
	and the ranking game next): hub link + centered mode label + streak header,
	plus the chrome the game screens share as :global classes scoped under the
	frame — the palette-ramp bar (.ramp-bar), the big buttons (.g-btn) and the
	status-colored hearts (.hearts). Sub-labels read var(--game-sub). -->
<script lang="ts">
	export let label = '';
	export let streak = 0;
	export let longStreak = false;
</script>

<main class="frame">
	<header class="top">
		<a class="hub-link" href="/game">
			<svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
				<path d="M10 3 L5 8 L10 13" stroke="currentColor" stroke-width="2" />
			</svg>
			Games
		</a>
		<span class="mode-label">{label}</span>
		<span class="streak">
			{#if streak > 0}🔥 {streak}{longStreak ? '-day streak' : ''}{/if}
		</span>
	</header>
	<slot />
</main>

<style>
	.frame {
		--game-sub: var(--color-text-light);
		position: relative;
		height: 100svh;
		max-width: 480px;
		margin: 0 auto;
		padding: 14px 18px calc(40px + env(safe-area-inset-bottom));
		display: flex;
		flex-direction: column;
		gap: 14px;
		overflow: hidden;
	}

	@media (prefers-color-scheme: dark) {
		.frame {
			--game-sub: var(--color-theme-lightgrey);
		}
	}

	.top {
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		align-items: center;
		font-size: var(--text-sm);
		flex-shrink: 0;
	}

	.hub-link {
		display: flex;
		align-items: center;
		gap: 5px;
		justify-self: start;
		font-weight: 700;
		letter-spacing: 1px;
		text-transform: uppercase;
		color: var(--accent-text);
		/* small type, but a thumb-sized hit area */
		padding: 14px 14px 14px 0;
		margin: -14px 0;
	}

	.hub-link svg {
		width: 12px;
		height: 12px;
	}

	.mode-label {
		color: var(--game-sub);
	}

	.streak {
		justify-self: end;
		font-weight: 700;
		white-space: nowrap;
	}

	.frame :global(.ramp-bar) {
		background: linear-gradient(
			90deg,
			rgb(var(--color-range-5)) 0%,
			rgb(var(--color-range-15)) 15%,
			rgb(var(--color-range-30)) 32%,
			rgb(var(--color-range-50)) 50%,
			rgb(var(--color-range-75)) 68%,
			rgb(var(--color-range-90)) 85%,
			rgb(var(--color-range-100)) 100%
		);
	}

	.frame :global(.g-btn) {
		height: 52px;
		border: none;
		background: none;
		cursor: pointer;
		font-family: inherit;
		font-size: var(--text-md);
		font-weight: 700;
		letter-spacing: 1px;
		text-transform: uppercase;
		color: var(--color-text);
	}

	.frame :global(.g-btn:disabled) {
		cursor: default;
		opacity: 0.6;
	}

	.frame :global(.g-btn.primary) {
		height: 56px;
		background: var(--highlight-text);
		color: var(--text-bg);
		box-shadow: 3px 3px 10px var(--color-theme-shadow);
	}

	.frame :global(.g-btn.ghost) {
		height: 48px;
		border: 1px solid var(--border-light);
	}

	.frame :global(.hearts) {
		color: var(--color-err);
		letter-spacing: 5px;
	}
</style>
