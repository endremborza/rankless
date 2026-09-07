// Orders overlapping async operations on one piece of state: each `claim()` starts a new operation
// and returns an `isCurrent()` that turns false once a later claim is made, so a slow earlier
// response is dropped after its await instead of clobbering the newer one.
export function createStaleGuard() {
	let latest = 0;
	return function claim() {
		const mine = ++latest;
		return () => mine === latest;
	};
}

export type IsCurrent = () => boolean;
