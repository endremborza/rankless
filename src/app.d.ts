// See https://kit.svelte.dev/docs/types#app
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		interface Locals {
			user: import('./lib/server/session').SessionUserData | null;
		}
		// interface Locals {}
		// interface PageData {}
		// interface Platform {}
	}
}

export {};
