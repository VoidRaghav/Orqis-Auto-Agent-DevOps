/**
 * Landing layout breakpoint. CSS, Nav, and matchMedia JS paths must agree.
 *
 * Layout/nav: 900px (this file + `@media (max-width: 900px)` in index.css)
 * GPU quality: 768px in device-tier.ts — layout ≠ GPU tier (intentionally separate)
 */
export const LAYOUT_MOBILE_MAX = 900;
export const LAYOUT_TIGHT_MAX = 480;

export const LAYOUT_MOBILE_MQ = `(max-width: ${LAYOUT_MOBILE_MAX}px)`;
export const LAYOUT_TIGHT_MQ = `(max-width: ${LAYOUT_TIGHT_MAX}px)`;

export function isLayoutMobile(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia(LAYOUT_MOBILE_MQ).matches;
}

/** Subscribe to layout mobile changes. Returns cleanup. */
export function onLayoutMobileChange(cb: (mobile: boolean) => void): () => void {
  if (typeof window === "undefined") return () => {};
  const mq = window.matchMedia(LAYOUT_MOBILE_MQ);
  const handler = () => cb(mq.matches);
  cb(mq.matches);
  mq.addEventListener("change", handler);
  return () => mq.removeEventListener("change", handler);
}
