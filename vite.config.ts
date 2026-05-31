import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [sveltekit()],
	server: { fs: { allow: ['static'] }, watch: { ignored: ['**/target/**'] } },
	ssr: { external: ['bun:sqlite'] },
	build: { rollupOptions: { external: ['bun:sqlite'] } },
	test: {
		include: ['src/**/*.test.ts']
	}
});
