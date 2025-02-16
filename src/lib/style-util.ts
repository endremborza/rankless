export function getColorArr(rate: number) {
	//const uRate = Math.pow(rate - 0.5, 2) * 4;
	//.map((x) => x.toFixed(0))
	const uRate = Math.abs(rate - 0.5) * 2;
	return [rate * 250, uRate * 220, 255 - rate * 250];
}

export function getColor(rate: number) {
	const nArr = getColorArr(rate);
	return `rgb(${nArr.join(', ')})`;
}

function colorGen() {
	let r = 0;
	const colorDefs = [];
	while (r < 1) {
		r += 0.05;
		colorDefs.push(
			`--color-range-${(r * 100).toFixed(0)}: ${getColorArr(r)
				.map((x) => x.toFixed(0))
				.join(', ')};`
		);
	}
	console.log(colorDefs.join('\n\t'));
}

//colorGen()
