/**
 * Headless core — pure domain types & logic, framework-agnostic.
 *
 * Rules (enforced via ESLint — see web/eslint.config.js core override):
 *  1. Files under `src/core/` MUST NOT import from `react`, `react-*`,
 *     `antd`, `@ant-design/*`, `zustand`, `@tanstack/react-query`,
 *     `axios`, or any other UI/framework package.
 *  2. Files under `src/core/` MUST NOT import from `@/components/*`,
 *     `@/pages/*`, `@/stores/*`, `@/hooks/*`, or `@/services/*`.
 *  3. External I/O is allowed only via **injected adapter interfaces**
 *     declared in `core/adapters.ts` — never via direct calls.
 *
 * This boundary preserves the option to later extract `core/` into a
 * separate `packages/core` pnpm workspace package (multica pattern)
 * without rewriting call sites.
 */
export * from './types/project';
export * from './types/session';
export * from './adapters';
