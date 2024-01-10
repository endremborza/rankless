<script lang="ts">
	type vType = string | number | boolean;

	export let values: [vType, vType] = ['On', 'Off'];
	export let labels: [string, string] = values.map((e) => (e.toString()));
	export let value: vType = values[0];
	export let pad = 5;
	export let height = 26;

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
		2 * pad}px; --height: {height}px; --full-height: {height + 2 * pad}px; --label: '{label}'"
>
	<input type="checkbox" bind:checked />
	<span class="slider round"
		>{#each labels as l}
			<div>{l}</div>
		{/each}</span
	>
</label>

<style>
	/* The switch - the box around the slider */
	.switch {
		position: relative;
		display: inline-block;
		width: var(--fw);
		height: var(--full-height);
	}

	/* Hide default HTML checkbox */
	.switch input {
		opacity: 0;
		width: 0;
		height: 0;
	}

	/* The slider */
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
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.slider > div {
		width: 50%;
		text-align: center;
	}

	.slider:before {
		position: absolute;
		content: var(--label);
		height: var(--height);
		width: var(--w);
		left: var(--pad);
		bottom: var(--pad);
		top: var(--pad);
		background-color: var(--color-theme-white);
		-webkit-transition: 0.4s;
		transition: 0.4s;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	input:checked + .slider {
		background-color: rgba(var(--color-range-15), 0.6);
	}

	input:checked + .slider:before {
		-webkit-transform: translateX(var(--tw));
		-ms-transform: translateX(var(--tw));
		transform: translateX(var(--tw));
	}

	/* Rounded sliders */
	.slider.round {
		border-radius: 34px;
	}

	.slider.round:before {
		border-radius: 34px;
	}
</style>
