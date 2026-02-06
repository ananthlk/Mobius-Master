# Mobius Style Guidelines

This folder is the **single source of truth** for Mobius branding and global styling. All agents and frontends should use it.

## Logo

- **Use** the logo from `mobius-design/assets/logo.svg` (light backgrounds) or `mobius-design/assets/logo-dark.svg` (dark backgrounds).
- **Do not** recreate the infinity/Mobius path elsewhere; reference these files or the shared logo spec (see below).
- The logo is a grey/white infinity symbol representing the Mobius strip. Keep the single continuous stroke and gradient (grey → white → grey).

## Design tokens

- **All Mobius UIs** should import `mobius-design/tokens.css` (and optionally `tokens-dark.css` for dark theme).
- **Prefer** `--mobius-*` CSS variables over local hex codes for colors, spacing, radius, and typography.
- Token categories: logo colors, text (primary/secondary/muted), backgrounds, borders, accent, status (success/warning/error), shadows, font stacks, type scale, spacing, radius.

## Do's and don'ts

- **Do** copy or symlink assets from `mobius-design/assets/` into your app's static/public folder, or reference via relative path from repo root.
- **Do** use `var(--mobius-accent)`, `var(--mobius-radius-base)`, etc. in new or updated styles.
- **Don't** duplicate the logo path or gradient in another SVG or component without consuming the shared logo spec.
- **Don't** introduce new global color or spacing values that conflict with the token set; extend the token set in `tokens.css` if needed.

## Logo spec (for programmatic SVG)

Apps that build the logo in code (e.g. extension with idle/processing states) should use `mobius-design/logo-spec.ts` (or `logo-spec.json`) for the path `d` and gradient stop colors so the logo stays in sync everywhere.
