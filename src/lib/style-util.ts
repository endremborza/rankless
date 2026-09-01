export function getColorArr(rate: number) {
	const uRate = Math.abs(rate - 0.5) * 2;
	return [rate * 250, uRate * 220, 255 - rate * 250];
}

export function getColor(rate: number) {
	const nArr = getColorArr(rate);
	return `rgb(${nArr.join(', ')})`;
}
