// See https://kit.svelte.dev/docs/types#app
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		interface Locals {
			user: import('./lib/server/session').SessionUserData | null;
			surveyShouldPrompt: boolean;
		}
		// interface Locals {}
		interface PageData {
			// Served by the (stat) layout for everything under it; see `loadMethodology`.
			methodology?: import('./lib/tree-types').Methodology | null;
		}
		// interface Platform {}
	}
}

export {};
