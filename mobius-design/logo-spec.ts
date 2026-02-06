/**
 * Mobius logo spec – path and colors for programmatic SVG (e.g. extension).
 * Single source of truth; do not duplicate elsewhere.
 */

export const MOBIUS_LOGO_VIEWBOX = '0 0 100 100';
export const MOBIUS_LOGO_STROKE_WIDTH = 4.5;

/** Infinity (Mobius) path – symmetric horizontal lemniscate, single continuous stroke */
export const MOBIUS_LOGO_PATH_D =
  'M 50 50 C 50 22 22 22 22 50 C 22 78 50 78 50 50 C 50 78 78 78 78 50 C 78 22 50 22 50 50';

export const MOBIUS_LOGO_GRADIENT_NORMAL = {
  start: '#4a4a4a',
  mid: '#e8e8e8',
  end: '#4a4a4a',
} as const;

export const MOBIUS_LOGO_GRADIENT_PROCESSING = {
  start: '#5a5a5a',
  mid: '#ffffff',
  end: '#5a5a5a',
} as const;
