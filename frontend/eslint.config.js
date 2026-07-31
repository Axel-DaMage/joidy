import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import svelte from 'eslint-plugin-svelte';
import globals from 'globals';

export default tseslint.config(
	// Global ignores
	{
		ignores: ['.svelte-kit/', 'build/', 'node_modules/', 'vite.config.ts']
	},

	// Base JS recommended rules
	js.configs.recommended,

	// TypeScript recommended (type-aware rules disabled for speed/simplicity)
	...tseslint.configs.recommended,

	// Svelte plugin
	...svelte.configs['flat/recommended'],

	// Configure Svelte parser to use TypeScript parser for <script lang="ts">
	// Also disable/relax TS rules that crash or error on Svelte's AST
	{
		files: ['**/*.svelte'],
		languageOptions: {
			parserOptions: {
				parser: tseslint.parser
			}
		},
		rules: {
			'@typescript-eslint/no-unused-vars': 'off',
			'@typescript-eslint/no-undef': 'off',
			'@typescript-eslint/no-explicit-any': 'warn',
			'@typescript-eslint/no-unused-expressions': 'warn'
		}
	},

	// Global settings for all files
	{
		languageOptions: {
			globals: {
				...globals.browser,
				...globals.node,
				...globals.es2022
			}
		},
		rules: {
			// Keep style issues as warnings rather than errors
			'no-unused-vars': 'warn',
			'no-undef': 'warn',
			'no-empty': 'warn',
			'no-console': 'warn',
			'no-useless-escape': 'warn',
			'no-prototype-builtins': 'warn',
			'prefer-const': 'warn',
			'no-var': 'warn',
			'object-shorthand': 'warn',
			'no-cond-assign': 'warn',
			'no-constant-condition': 'warn',
			'no-debugger': 'warn',
			'no-redeclare': 'warn',
			'no-self-assign': 'warn',
			'no-unused-labels': 'warn',
			'no-useless-catch': 'warn',
			'no-useless-assignment': 'warn',
			'no-case-declarations': 'warn'
		}
	},

	// TypeScript-specific relaxations
	{
		files: ['**/*.ts', '**/*.js'],
		rules: {
			'@typescript-eslint/no-unused-vars': 'warn',
			'@typescript-eslint/no-explicit-any': 'warn',
			'@typescript-eslint/no-empty-object-type': 'warn',
			'@typescript-eslint/no-unused-expressions': 'warn',
			'@typescript-eslint/no-require-imports': 'warn',
			'@typescript-eslint/no-empty-interface': 'off',
			'@typescript-eslint/ban-ts-comment': 'warn',
			'@typescript-eslint/no-wrapper-object-types': 'warn'
		}
	},

	// Svelte-specific relaxations
	{
		files: ['**/*.svelte'],
		rules: {
			'svelte/no-at-html-tags': 'warn',
			'svelte/no-inner-declarations': 'warn',
			'svelte/no-unused-svelte-ignore': 'warn',
			'svelte/no-target-blank': 'warn',
			'svelte/valid-compile': 'warn',
			'svelte/require-each-key': 'warn',
			'svelte/no-navigation-without-resolve': 'warn',
			'svelte/prefer-svelte-reactivity': 'warn',
			'svelte/infinite-reactive-loop': 'warn',
			'svelte/no-reactive-reassign': 'warn',
			'svelte/no-immutable-reactive-statements': 'warn'
		}
	}
);
