<script lang="ts">
	type vType = string | number | boolean;

	export let values: [vType, vType] = ['On', 'Off'];
	export let labels: [string, string] = values.map((e) => e.toString());
	export let value: vType = values[0];
	export let pad = 5;
	export let height = 60;

	export let width: number | undefined = undefined;

	let checked = value == values[1];

	$: label = checked ? labels[1] : labels[0];

	const change = (ch: boolean) => {
		value = ch ? values[1] : values[0];
	};

	$: change(checked);

	function getWidth(labels: [string, string]) {
		return (
			((labels[0].length > labels[1].length ? labels[0].length : labels[1].length) * 0.8 + 2) * 20
		);
	}

	$: w = width || getWidth(labels);
</script>

<label
	class="switch"
	style="--pad: {pad}px; --fw: {w}px; --w: {w / 2}px;  --tw: {w / 2 -
		2 * pad}px; --height: {height}px;  --hh: {height / 2}px;--full-height: {height +
		2 * pad}px; --label: '{label}'"
>
	<span class="tg-bg" />
	<input type="checkbox" bind:checked />
	<span class="slider round"
		>{#each labels as l}
			<div>{l}</div>
		{/each}
	</span>
</label>

<style>
	/* The switch - the box around the slider */
	.switch {
		position: relative;
		display: inline-block;
		width: var(--fw);
		height: var(--full-height);
	}

	.switch input {
		opacity: 0;
		width: 0;
		height: 0;
	}

	.slider {
		position: absolute;
		cursor: pointer;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		-webkit-transition: 0.4s;
		transition: 0.4s;
		background-color: rgba(var(--color-range-35), 0.6);
		background-image: linear-gradient(
			to bottom,
			rgba(0, 0, 0, 0) 0%,
			rgba(0, 0, 0, 0) 50%,
			rgba(0, 0, 0, 0.1) 51%
		);
		display: flex;
		flex-direction: column;
		justify-content: space-around;
		align-items: start;
		padding-left: 20px;
	}

	.slider > div {
		width: 80%;
		text-align: left;
		font-size: 23px;
		font-weight: 500;
	}

	.slider:before {
		position: absolute;
		content: '';
		height: calc(var(--hh) - 2 * var(--pad));
		width: calc(var(--hh) - 2 * var(--pad));
		right: calc(var(--pad) * 2);
		top: calc(var(--pad) * 2);
		border-radius: calc((var(--hh) - var(--pad)) / 2);
		background-color: var(--color-theme-white);
		-webkit-transition: 0.4s;
		transition: 0.4s;
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 5;
	}

	.tg-bg {
		position: absolute;
		cursor: pointer;
		content: '';
		height: var(--height);
		width: var(--hh);
		right: var(--pad);
		top: var(--pad);
		border-radius: calc(var(--hh) / 2);
		background-color: var(--color-theme-darkgrey2);
		-webkit-transition: 0.4s;
		transition: 0.4s;
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1;
	}

	input:checked + .slider {
		background-color: rgba(var(--color-range-15), 0.6);
		background-image: linear-gradient(
			to bottom,
			rgba(0, 0, 0, 0.1) 0%,
			rgba(0, 0, 0, 0.1) 50%,
			rgba(0, 0, 0, 0) 51%
		);
	}

	input:checked + .slider:before {
		-webkit-transform: translateY(var(--hh));
		-ms-transform: translateY(var(--hh));
		transform: translateY(var(--hh));
	}

	.slider.round {
		border-radius: calc(var(--hh) / 2);
	}
</style>
