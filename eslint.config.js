import js from '@eslint/js';
import ts from 'typescript-eslint';
import svelte from 'eslint-plugin-svelte';
import prettier from 'eslint-config-prettier';
import globals from 'globals';
import svelteConfig from './svelte.config.js';

export default ts.config(
	{
		ignores: [
			'build/',
			'.svelte-kit/',
			'package/',
			'dist/',
			'.venv/',
			'target/',
			'coverage/',
			'coverage-e2e/'
		]
	},
	js.configs.recommended,
	...ts.configs.recommended,
	...svelte.configs.recommended,
	prettier,
	...svelte.configs.prettier,
	{
		languageOptions: {
			globals: { ...globals.browser, ...globals.node }
		},
		rules: {
			'no-undef': 'off',
			// All {@html} sites render trusted backend/generated markup (entity names with
			// sub/sup/i, generated prose, JSON-LD). Disabled instead of scattering ignores.
			'svelte/no-at-html-tags': 'off',
			// Conflicts with inherently-external links and the existing base-prepend link
			// helpers (entToLink); satisfying it would require a routing refactor.
			'svelte/no-navigation-without-resolve': 'off',
			// Both rules assume runes-mode reactivity. These components are legacy mode, where
			// the compiler resolves template/`$:` deps statically and `untrack`s the call — so a
			// `$:`-defined function (reassigned when its closed-over reactive vars change) is what
			// drives dependent re-eval, and a mutated SvelteSet/Map (not reassigned) is NOT tracked.
			// "Fixing" these silently breaks reactivity; keep the legacy `$:` / reassign patterns.
			'svelte/no-reactive-functions': 'off',
			'svelte/prefer-svelte-reactivity': 'off'
		}
	},
	{
		files: ['**/*.svelte', '**/*.svelte.ts', '**/*.svelte.js'],
		languageOptions: {
			parserOptions: {
				extraFileExtensions: ['.svelte'],
				parser: ts.parser,
				svelteConfig
			}
		},
		// `export let` props read as unused, and the rule crashes on the Svelte AST.
		rules: { '@typescript-eslint/no-unused-vars': 'off' }
	}
);
