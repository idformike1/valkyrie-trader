/**
 * Valkyrie Design System V3 — Typography Scale
 * Strictly controls the typography styles across all terminal workspaces.
 */

export const TYPOGRAPHY = {
  display: "font-sans text-[28px] font-semibold tracking-tight text-main",
  heading: "font-sans text-[16px] font-semibold tracking-normal text-main",
  section: "font-sans text-[13px] font-semibold tracking-normal text-slate-400",
  body: "font-sans text-[12px] font-normal tracking-normal text-slate-200",
  meta: "font-sans text-[11px] font-normal tracking-normal text-slate-500",
  mono: "font-mono text-[11px] font-normal tracking-tight tabular-nums",
} as const;

export type TypographyVariant = keyof typeof TYPOGRAPHY;

/**
 * Returns the tailwind classes for the specified typography variant.
 * If fallback to monospace is true, it overrides the family mapping.
 */
export function getTypographyClass(variant: TypographyVariant, useMono: boolean = false): string {
  if (variant === "mono" || useMono) {
    // Monospace is only allowed for IDs, timestamps, prices, and logs.
    const base = TYPOGRAPHY[variant === "mono" ? "mono" : variant];
    return base.replace("font-sans", "font-mono");
  }
  return TYPOGRAPHY[variant];
}
