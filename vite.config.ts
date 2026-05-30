import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig, type UserConfig } from 'vite';
import type { TestUserConfig } from 'vitest/config';

export default defineConfig({
	plugins: [sveltekit()],
	server: { fs: { allow: ['static'] }, watch: { ignored: ['**/target/**'] } },
	ssr: { external: ['bun:sqlite'] },
	build: { rollupOptions: { external: ['bun:sqlite'] } },
	test: {
		include: ['src/**/*.test.ts'],
		alias: {
			'$lib': '/src/lib',
			'$app': '/src/app'
		}
	}
} as UserConfig & { test: TestUserConfig });
