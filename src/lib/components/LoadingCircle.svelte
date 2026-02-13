<script lang="ts">
	export let delay = 800;
	export let isArming: boolean = false;
</script>

{#if isArming && delay > 100}
	<div class="loading-circle" style="--duration: {delay}ms">
		<svg viewBox="0 0 24 24">
			<circle class="ring" cx="12" cy="12" r="9" pathLength="100" />
		</svg>
	</div>
{/if}

<style>
	.loading-circle {
		--color: var(--accent-text, #3b82f6);
		--size: 24px;
		--stroke: 2.5px;

		width: var(--size);
		height: var(--size);

		opacity: 0;
		animation: fadeIn 120ms ease forwards;
	}

	svg {
		width: 100%;
		height: 100%;
		transform: rotate(-90deg); /* start at top */
	}

	.ring {
		fill: none;
		stroke: var(--color);
		stroke-width: var(--stroke);
		stroke-linecap: round;

		stroke-dasharray: 0 100;
		animation: draw var(--duration) linear forwards;
	}

	@keyframes draw {
		from {
			stroke-dasharray: 0 100;
		}
		to {
			stroke-dasharray: 100 0;
		}
	}

	@keyframes fadeIn {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}
</style>
