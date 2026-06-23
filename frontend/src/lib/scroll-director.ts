/** Single scroll-film director — 8 chapters, fluid + loop uniforms. */

export type FilmChapter =
  | "splash"
  | "break"
  | "blind"
  | "burn"
  | "patch"
  | "ship"
  | "control"
  | "finale";

export type FluidState = "void" | "spawn" | "blind" | "burn" | "patch" | "ship" | "clear";

export type ChapterDef = {
  id: FilmChapter;
  label: string;
  start: number;
  end: number;
  headline: string;
  sub?: string;
  ghostWord?: string;
};

export const FILM_CHAPTERS: ChapterDef[] = [
  { id: "splash", label: "01", start: 0, end: 0.08, headline: "ORQIS" },
  {
    id: "break",
    label: "02",
    start: 0.08,
    end: 0.25,
    headline: "Agents break in prod.",
    sub: "Orqis ships the fix.",
  },
  {
    id: "blind",
    label: "03",
    start: 0.25,
    end: 0.4,
    headline: "You're blind.",
    sub: "Raw stack traces. No file. No line.",
    ghostWord: "BLIND",
  },
  {
    id: "burn",
    label: "04",
    start: 0.4,
    end: 0.55,
    headline: "$847/hr burn.",
    sub: "23 API calls in 4 seconds.",
    ghostWord: "BURN",
  },
  {
    id: "patch",
    label: "05",
    start: 0.55,
    end: 0.7,
    headline: "Patch validated.",
    sub: "Deterministic loop guard + diff verification.",
    ghostWord: "PATCH",
  },
  {
    id: "ship",
    label: "06",
    start: 0.7,
    end: 0.85,
    headline: "PR #1 ready.",
    sub: "Review on GitHub. Never writes to main.",
    ghostWord: "SHIP",
  },
  {
    id: "control",
    label: "07",
    start: 0.85,
    end: 0.95,
    headline: "Mission control.",
    sub: "Live console · changes · audit trail",
  },
  {
    id: "finale",
    label: "08",
    start: 0.95,
    end: 1,
    headline: "Connect GitHub.",
    sub: "Ship fixes from any IDE.",
  },
];

export type FluidUniforms = {
  density: number;
  speed: number;
  turbulence: number;
  colorA: [number, number, number];
  colorB: [number, number, number];
  colorC: [number, number, number];
  opacity: number;
  crystallize: number;
  heat: number;
  fog: number;
};

export type DirectorState = {
  progress: number;
  chapterIndex: number;
  chapter: FilmChapter;
  chapterT: number;
  chapterLocal: number;
  fluidState: FluidState;
  fluidUniforms: FluidUniforms;
  loopIntensity: number;
  loopSpin: number;
  loopFracture: number;
  chromaticAberration: number;
  bloomIntensity: number;
};

function clamp01(v: number) {
  return Math.max(0, Math.min(1, v));
}

function easeInOut(t: number) {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function lerp3(a: [number, number, number], b: [number, number, number], t: number): [number, number, number] {
  return [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
}

const VIRIDIAN: [number, number, number] = [0.1, 0.24, 0.19];
const IVORY: [number, number, number] = [0.96, 0.94, 0.91];
const AMBER: [number, number, number] = [0.91, 0.63, 0.27];
const HEAL: [number, number, number] = [0.24, 0.86, 0.59];
const TEAL: [number, number, number] = [0.2, 0.72, 0.68];
const GREY: [number, number, number] = [0.35, 0.38, 0.4];

function fluidForChapter(chapter: FilmChapter, t: number): FluidUniforms {
  const e = easeInOut(t);
  switch (chapter) {
    case "splash":
      return {
        density: lerp(0.02, 0.12, e),
        speed: 0.15,
        turbulence: 0.2,
        colorA: VIRIDIAN,
        colorB: TEAL,
        colorC: IVORY,
        opacity: lerp(0.1, 0.35, e),
        crystallize: 0,
        heat: 0,
        fog: 0.6,
      };
    case "break":
      return {
        density: lerp(0.2, 0.45, e),
        speed: 0.35,
        turbulence: 0.45,
        colorA: VIRIDIAN,
        colorB: TEAL,
        colorC: IVORY,
        opacity: lerp(0.35, 0.55, e),
        crystallize: 0,
        heat: 0.1,
        fog: 0.45,
      };
    case "blind":
      return {
        density: lerp(0.5, 0.72, e),
        speed: 0.55,
        turbulence: 0.65,
        colorA: GREY,
        colorB: VIRIDIAN,
        colorC: IVORY,
        opacity: lerp(0.55, 0.68, e),
        crystallize: 0,
        heat: 0,
        fog: 0.75,
      };
    case "burn":
      return {
        density: 0.68,
        speed: 0.85,
        turbulence: 0.9,
        colorA: AMBER,
        colorB: [0.95, 0.35, 0.15],
        colorC: VIRIDIAN,
        opacity: 0.72,
        crystallize: 0,
        heat: lerp(0.4, 1, e),
        fog: 0.5,
      };
    case "patch":
      return {
        density: lerp(0.65, 0.5, e),
        speed: 0.4,
        turbulence: 0.35,
        colorA: HEAL,
        colorB: TEAL,
        colorC: IVORY,
        opacity: lerp(0.65, 0.55, e),
        crystallize: lerp(0, 0.85, e),
        heat: lerp(0.8, 0.2, e),
        fog: 0.35,
      };
    case "ship":
      return {
        density: lerp(0.45, 0.3, e),
        speed: 0.28,
        turbulence: 0.22,
        colorA: HEAL,
        colorB: TEAL,
        colorC: IVORY,
        opacity: lerp(0.5, 0.38, e),
        crystallize: lerp(0.85, 0.4, e),
        heat: 0,
        fog: 0.25,
      };
    case "control":
      return {
        density: 0.22,
        speed: 0.18,
        turbulence: 0.15,
        colorA: VIRIDIAN,
        colorB: TEAL,
        colorC: IVORY,
        opacity: 0.32,
        crystallize: 0.2,
        heat: 0,
        fog: 0.2,
      };
    case "finale":
      return {
        density: lerp(0.18, 0.05, e),
        speed: 0.12,
        turbulence: 0.1,
        colorA: VIRIDIAN,
        colorB: TEAL,
        colorC: IVORY,
        opacity: lerp(0.28, 0.12, e),
        crystallize: 0,
        heat: 0,
        fog: lerp(0.15, 0.05, e),
      };
    default:
      return fluidForChapter("break", 0);
  }
}

function loopForChapter(chapter: FilmChapter, t: number) {
  const e = easeInOut(t);
  switch (chapter) {
    case "splash":
      return { intensity: lerp(0.05, 0.25, e), spin: 0.2, fracture: 0 };
    case "break":
      return { intensity: lerp(0.35, 1, e), spin: lerp(0.4, 1.2, e), fracture: 0 };
    case "blind":
      return { intensity: 1, spin: lerp(1.2, 2.4, e), fracture: 0 };
    case "burn":
      return { intensity: 1, spin: lerp(2.4, 3.2, e), fracture: lerp(0, 0.15, e) };
    case "patch":
      return { intensity: lerp(1, 0.75, e), spin: lerp(3.2, 1.8, e), fracture: lerp(0.15, 0.65, e) };
    case "ship":
      return { intensity: lerp(0.75, 0.45, e), spin: lerp(1.8, 0.6, e), fracture: lerp(0.65, 0.9, e) };
    case "control":
      return { intensity: 0.35, spin: 0.4, fracture: 0.85 };
    case "finale":
      return { intensity: lerp(0.3, 0.1, e), spin: lerp(0.4, 0.1, e), fracture: lerp(0.85, 1, e) };
    default:
      return { intensity: 0.5, spin: 1, fracture: 0 };
  }
}

function fluidStateFor(chapter: FilmChapter): FluidState {
  const map: Record<FilmChapter, FluidState> = {
    splash: "void",
    break: "spawn",
    blind: "blind",
    burn: "burn",
    patch: "patch",
    ship: "ship",
    control: "clear",
    finale: "clear",
  };
  return map[chapter];
}

export function resolveChapter(progress: number): {
  chapterIndex: number;
  chapter: FilmChapter;
  chapterT: number;
} {
  const p = clamp01(progress);
  for (let i = FILM_CHAPTERS.length - 1; i >= 0; i--) {
    const ch = FILM_CHAPTERS[i];
    if (p >= ch.start - 0.0001) {
      const span = Math.max(0.0001, ch.end - ch.start);
      const local = clamp01((p - ch.start) / span);
      return { chapterIndex: i, chapter: ch.id, chapterT: local };
    }
  }
  return { chapterIndex: 0, chapter: "splash", chapterT: 0 };
}

export function resolveDirector(progress: number): DirectorState {
  const p = clamp01(progress);
  const { chapterIndex, chapter, chapterT } = resolveChapter(p);
  const ch = FILM_CHAPTERS[chapterIndex];
  const loop = loopForChapter(chapter, chapterT);
  const fluidUniforms = fluidForChapter(chapter, chapterT);

  let chromatic = 0;
  let bloom = 0.35;
  if (chapter === "burn") {
    chromatic = lerp(0, 0.45, easeInOut(chapterT));
    bloom = lerp(0.4, 0.75, easeInOut(chapterT));
  } else if (chapter === "break") {
    bloom = lerp(0.35, 0.55, easeInOut(chapterT));
  } else if (chapter === "finale") {
    bloom = lerp(0.45, 0.65, easeInOut(chapterT));
  }

  return {
    progress: p,
    chapterIndex,
    chapter,
    chapterT,
    chapterLocal: ch.start + (ch.end - ch.start) * chapterT,
    fluidState: fluidStateFor(chapter),
    fluidUniforms,
    loopIntensity: loop.intensity,
    loopSpin: loop.spin,
    loopFracture: loop.fracture,
    chromaticAberration: chromatic,
    bloomIntensity: bloom,
  };
}

export function chapterProgressToScrollY(progress: number, zoneHeight: number): number {
  const scrollable = zoneHeight - (typeof window !== "undefined" ? window.innerHeight : 800);
  return clamp01(progress) * Math.max(0, scrollable);
}

export function scrollToChapter(chapterId: FilmChapter, zoneEl: HTMLElement) {
  const ch = FILM_CHAPTERS.find((c) => c.id === chapterId);
  if (!ch || typeof window === "undefined") return;
  const rect = zoneEl.getBoundingClientRect();
  const scrollable = rect.height - window.innerHeight;
  const target = ch.start * scrollable + zoneEl.offsetTop;
  window.scrollTo({ top: target, behavior: "smooth" });
}
