import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';

// Lenient, fast (no type-checking) flat config. The goal is a RUNNABLE lint gate
// over src/, not a zero-warning cleanup of a previously-unlinted codebase. Noisy
// rules that the existing code trips on are dialed down to 'warn' or 'off'; the
// real-bug rules (react-hooks/rules-of-hooks, no-undef via TS) stay on.
export default tseslint.config(
  {
    ignores: [
      'build/**',
      'dist/**',
      'node_modules/**',
      'public/**',
      '.worktrees/**',
      'graphify-out/**',
      'graphify-comparison/**',
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['src/**/*.{ts,tsx,js,jsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.browser },
    },
    plugins: { 'react-hooks': reactHooks },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      // Pre-existing patterns in this codebase — report, don't block.
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-unused-vars': [
        'warn',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      'no-unused-vars': 'off',
      'no-empty': 'warn',
      'no-constant-condition': ['warn', { checkLoops: false }],
    },
  },
);
