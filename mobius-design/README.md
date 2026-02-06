# Mobius Design

Shared branding and style tokens for all Mobius UIs.

## Contents

- **`assets/logo.svg`** – Canonical Mobius infinity logo (grey/white), for light backgrounds.
- **`assets/logo-dark.svg`** – Same logo with lighter stroke, for dark backgrounds.
- **`tokens.css`** – CSS custom properties (colors, typography, spacing, radius) for light theme.
- **`tokens-dark.css`** – Dark theme overrides; apply with `.dark` or `[data-theme="dark"]`.
- **`STYLE_GUIDELINES.md`** – Rules for logo usage and tokens (for humans and agents).
- **`logo-spec.ts`** – Path and colors for programmatic logo (e.g. extension).

## How to consume

1. **Static assets**: Copy or symlink `assets/logo.svg` (or `logo-dark.svg`) into your app’s static/public directory, or reference via relative path (e.g. `../../mobius-design/assets/logo.svg` from a frontend).
2. **Tokens**: In your main CSS, `@import` or link to `tokens.css`. For dark UIs, also include `tokens-dark.css` and add the appropriate class/attribute to the root.
3. **Programmatic logo**: If you build the logo in JS/TS (e.g. with animation), import path and colors from `logo-spec.ts` so the logo stays in sync.

See **STYLE_GUIDELINES.md** for full rules.
