<script lang="ts">
	import { onMount, tick } from 'svelte';

	// One tooltip for every "what is this?" affordance in the app. The trigger is a small "i" badge by
	// default (`kind="icon"`) or the wrapped text itself (`kind="inline"`, e.g. the word "indexed"). It
	// opens on hover/focus for pointer + keyboard, and on tap for touch, and is positioned right at the
	// trigger with a solid, readable background (clamped into the viewport, flipping below when needed).
	export let text = '';
	export let label = 'More information';
	export let kind: 'icon' | 'inline' = 'icon';

	let open = false;
	let triggerEl: HTMLButtonElement;
	let tipEl: HTMLDivElement;
	let tipX = 0;
	let tipY = 0;
	let below = false;

	async function place() {
		if (!triggerEl) return;
		const r = triggerEl.getBoundingClientRect();
		const cx = r.left + r.width / 2;
		tipX = cx;
		tipY = r.top;
		below = false;
		await tick();
		if (!tipEl) return;
		const margin = 8;
		const w = tipEl.offsetWidth;
		const h = tipEl.offsetHeight;
		tipX = Math.min(Math.max(cx, w / 2 + margin), window.innerWidth - w / 2 - margin);
		// The sticky header occludes the top of the viewport, so the safe ceiling for an above-trigger tip
		// is the header's bottom, not 0 — otherwise a near-top trigger (e.g. "indexed") flips its tip up
		// into the header band where it's painted over. Below that ceiling, drop the tip beneath instead.
		const headerH =
			parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--header-height')) ||
			0;
		below = r.top - h - margin < headerH + margin;
		tipY = below ? r.bottom + margin : r.top - margin;
	}

	async function show() {
		open = true;
		await place();
	}
	function hide() {
		open = false;
	}
	// Pointer-enter only reacts to a real mouse: on touch the tap is handled by click, so we avoid the
	// synthesized mouseenter→click sequence cancelling itself out.
	function onPointerEnter(e: PointerEvent) {
		if (e.pointerType === 'mouse') show();
	}
	function onPointerLeave(e: PointerEvent) {
		if (e.pointerType === 'mouse') hide();
	}

	onMount(() => {
		const onDocPointer = (e: Event) => {
			if (!open) return;
			const t = e.target as Node;
			if (triggerEl?.contains(t) || tipEl?.contains(t)) return;
			hide();
		};
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape') hide();
		};
		const onScroll = () => hide();
		document.addEventListener('pointerdown', onDocPointer, true);
		document.addEventListener('keydown', onKey);
		window.addEventListener('scroll', onScroll, true);
		window.addEventListener('resize', onScroll);
		return () => {
			document.removeEventListener('pointerdown', onDocPointer, true);
			document.removeEventListener('keydown', onKey);
			window.removeEventListener('scroll', onScroll, true);
			window.removeEventListener('resize', onScroll);
		};
	});
</script>

<button
	type="button"
	class="info-trigger {kind}"
	bind:this={triggerEl}
	aria-label={label}
	aria-expanded={open}
	on:pointerenter={onPointerEnter}
	on:pointerleave={onPointerLeave}
	on:focus={show}
	on:blur={hide}
	on:click|preventDefault|stopPropagation={show}
>
	{#if kind === 'icon'}<span class="info-i">i</span>{:else}<slot />{/if}
</button>

{#if open}
	<div
		class="info-tip"
		class:below
		bind:this={tipEl}
		style="left:{tipX}px; top:{tipY}px;"
		role="tooltip"
	>
		<slot name="text">{text}</slot>
	</div>
{/if}

<style>
	.info-trigger {
		font: inherit;
		color: inherit;
		background: none;
		border: none;
		padding: 0;
		margin: 0;
		cursor: pointer;
		vertical-align: baseline;
	}

	.info-trigger.inline {
		text-decoration: underline dotted;
		text-underline-offset: 2px;
	}

	.info-i {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.4em;
		height: 1.4em;
		font-size: var(--text-xs);
		font-style: italic;
		line-height: 1;
		border: 1px solid currentColor;
		border-radius: 50%;
		opacity: 0.65;
		transition: opacity 0.15s;
	}

	.info-trigger:hover .info-i,
	.info-trigger:focus-visible .info-i {
		opacity: 1;
	}

	/* Inverse pill: text color on the page's text-bg reads cleanly in both light and dark themes
	   (mirrors the .tile-badge pattern). Fixed-positioned and clamped by `place()`. */
	.info-tip {
		position: fixed;
		transform: translateX(-50%) translateY(-100%);
		max-width: min(300px, calc(100vw - 16px));
		padding: 7px 10px;
		font-size: var(--text-xs);
		font-weight: 400;
		line-height: 1.4;
		text-align: left;
		color: var(--text-bg);
		background: var(--color-text);
		box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
		z-index: 100;
		pointer-events: none;
	}

	.info-tip.below {
		transform: translateX(-50%) translateY(0);
	}
</style>
