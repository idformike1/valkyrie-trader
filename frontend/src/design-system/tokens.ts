export const SPACING = {
  px2: 2,
  px4: 4,
  px8: 8,
  px12: 12,
  px16: 16,
  px24: 24,
  px32: 32,
  px48: 48,
  px64: 64,
} as const;

export type SpacingToken = keyof typeof SPACING;

export const BORDER_RADIUS = {
  px4: 4,
  px6: 6,
  px8: 8,
  px12: 12,
} as const;

export type BorderRadiusToken = keyof typeof BORDER_RADIUS;

export const SHADOWS = {
  none: "none",
  subtle: "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
  elevated: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)",
} as const;

export type ShadowToken = keyof typeof SHADOWS;

export const PANEL_PADDING = {
  compact: 12,
  standard: 16,
  large: 24,
} as const;

export type PanelPaddingVariant = keyof typeof PANEL_PADDING;
