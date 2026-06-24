"use client";

import { useEffect, useState } from "react";
import { FILM_CHAPTERS, scrollToChapter, type FilmChapter } from "@/lib/scroll-director";
import { useRobotFlowOptional } from "@/components/RobotFlowContext";
import { colors, fonts } from "@/lib/tokens";

export default function ChapterNav({
  zoneRef,
}: {
  zoneRef: React.RefObject<HTMLDivElement | null>;
}) {
  const flow = useRobotFlowOptional();
  const [active, setActive] = useState<FilmChapter>("splash");
  const [visible, setVisible] = useState(false);
  const reducedMotion =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    if (!flow) return;
    let raf = 0;
    const tick = () => {
      const d = flow.directorRef.current;
      if (d) {
        setActive(d.chapter);
        setVisible(d.progress > 0.06 && d.chapter !== "splash");
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [flow]);

  if (!visible) return null;

  const chapters = FILM_CHAPTERS.filter((c) => c.id !== "splash");

  return (
    <nav className="chapter-nav" aria-label="Film chapters">
      <div className="chapter-nav-arc" aria-hidden>
        {chapters.map((ch) => (
          <button
            key={ch.id}
            type="button"
            className={`chapter-nav-dot${active === ch.id ? " chapter-nav-dot--active" : ""}`}
            aria-label={`Chapter ${ch.label}: ${ch.headline}`}
            aria-current={active === ch.id ? "step" : undefined}
            onClick={() => {
              if (zoneRef.current) {
                scrollToChapter(ch.id, zoneRef.current);
              }
            }}
          >
            <span className="chapter-nav-dot-inner" />
            <span className="chapter-nav-label" style={{ fontFamily: fonts.mono }}>
              {ch.label}
            </span>
          </button>
        ))}
      </div>
      {reducedMotion && (
        <p className="chapter-nav-hint" style={{ fontFamily: fonts.mono, color: colors.muted }}>
          Jump chapters
        </p>
      )}
    </nav>
  );
}
