/** DOM panel registry — robot tracks visible text/widgets while scrolling. */

export type PanelEntry = {
  id: string;
  section: string;
  el: HTMLElement;
  accent: string;
  /** Higher = preferred look target (left copy blocks should win) */
  priority?: number;
};

const panels = new Map<string, PanelEntry>();

export function registerPanel(entry: PanelEntry) {
  panels.set(entry.id, entry);
}

export function unregisterPanel(id: string) {
  panels.delete(id);
}

function effectiveOpacity(el: HTMLElement): number {
  let op = 1;
  let node: HTMLElement | null = el;
  while (node && node !== document.documentElement) {
    const style = window.getComputedStyle(node);
    if (style.display === "none" || style.visibility === "hidden") return 0;
    op *= parseFloat(style.opacity) || 1;
    if (op < 0.04) return 0;
    node = node.parentElement;
  }
  return op;
}

export type LookAtTarget = {
  x: number;
  y: number;
  strength: number;
  /** -1 left .. 1 right in viewport */
  nx: number;
  ny: number;
};

export function getActiveLookAtTarget(): LookAtTarget | null {
  if (typeof window === "undefined") return null;

  const vh = window.innerHeight;
  const vw = window.innerWidth;

  let best: LookAtTarget | null = null;
  let bestScore = 0;

  for (const entry of Array.from(panels.values())) {
    const { el, priority = 1 } = entry;
    const effOp = effectiveOpacity(el);
    if (effOp < 0.28) continue;

    const rect = el.getBoundingClientRect();
    if (rect.bottom < vh * 0.05 || rect.top > vh * 0.95) continue;

    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;

    const visTop = Math.max(0, rect.top);
    const visBot = Math.min(vh, rect.bottom);
    const visH = visBot - visTop;
    if (visH <= 0) continue;

    const ratio = visH / Math.max(rect.height, 1);
    const centerBias = 1 - Math.abs(cy - vh * 0.44) / (vh * 0.52);
    const isLeft = cx < vw * 0.48;
    const leftBoost = isLeft ? 1.85 : 0.55;
    const score = ratio * Math.max(0.12, centerBias) * leftBoost * priority * effOp;

    if (score > bestScore) {
      bestScore = score;
      best = {
        x: cx,
        y: cy,
        strength: score,
        nx: cx / vw,
        ny: cy / vh,
      };
    }
  }

  return best;
}
