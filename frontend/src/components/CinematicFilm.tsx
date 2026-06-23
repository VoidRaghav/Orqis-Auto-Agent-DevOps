"use client";

import { useEffect, useRef, useState } from "react";
import { useRobotFlowOptional } from "@/components/RobotFlowContext";
import { FILM_CHAPTERS, type FilmChapter } from "@/lib/scroll-director";
import { registerPanel, unregisterPanel } from "@/lib/panel-registry";
import { colors, fonts } from "@/lib/tokens";

const FILM_SCROLL_VH = 420;

const CHAPTER_ACCENT: Partial<Record<FilmChapter, string>> = {
  blind: colors.ivory,
  burn: colors.amber,
  patch: colors.heal,
  ship: colors.phosphor,
};

const VISIBLE_CHAPTERS: FilmChapter[] = ["blind", "burn", "patch", "ship"];

export default function CinematicFilm() {
  const flow = useRobotFlowOptional();
  const wrapRef = useRef<HTMLDivElement>(null);
  const headlineRef = useRef<HTMLHeadingElement>(null);
  const [display, setDisplay] = useState<(typeof FILM_CHAPTERS)[number] | null>(null);
  const [opacity, setOpacity] = useState(0);

  useEffect(() => {
    if (!flow) return;
    let raf = 0;
    const tick = () => {
      const d = flow.directorRef.current;
      if (!d || !VISIBLE_CHAPTERS.includes(d.chapter)) {
        setOpacity(0);
        raf = requestAnimationFrame(tick);
        return;
      }
      const ch = FILM_CHAPTERS.find((c) => c.id === d.chapter)!;
      setDisplay(ch);
      const edge = Math.min(d.chapterT, 1 - d.chapterT);
      const fade = Math.min(1, edge * 5);
      setOpacity(fade * 0.95);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [flow]);

  const accent = display ? CHAPTER_ACCENT[display.id] ?? colors.ivory : colors.ivory;

  useEffect(() => {
    const el = headlineRef.current;
    if (!el || !display) return;
    const id = `film-${display.id}`;
    registerPanel({
      id,
      section: "film",
      el,
      accent,
      priority: 2,
    });
    return () => unregisterPanel(id);
  }, [display, accent]);

  return (
    <div
      ref={wrapRef}
      className="cinematic-film-scroll"
      style={{ height: `${FILM_SCROLL_VH}vh` }}
      aria-hidden={opacity < 0.05}
    >
      <div className="cinematic-film-stage">
        {display?.ghostWord && (
          <div
            className="cinematic-film-ghost"
            style={{ opacity: opacity * 0.55, color: accent }}
            aria-hidden
          >
            {display.ghostWord}
          </div>
        )}

        <div className="cinematic-film-copy" style={{ opacity }}>
          <p className="cinematic-film-kicker" style={{ fontFamily: fonts.mono, color: colors.muted }}>
            [{display?.label ?? "03"} / 08]
          </p>
          <h2
            ref={headlineRef}
            className="cinematic-film-headline editorial-headline"
            style={{ color: colors.ivory }}
          >
            {display?.headline}
          </h2>
          {display?.sub && (
            <p className="cinematic-film-sub" style={{ fontFamily: fonts.serif, color: colors.muted }}>
              {display.sub}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
