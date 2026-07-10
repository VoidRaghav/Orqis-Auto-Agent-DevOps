import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { gsap } from "gsap";
import MetaLabel from "@/components/ui/MetaLabel";
import { colors, fonts } from "@/lib/tokens";
import { useLayoutMobile } from "@/hooks/useLayoutMobile";
import { LAYOUT_TIGHT_MQ } from "@/lib/layout-breakpoint";

const LINKS = [
  // `enter` is the fraction of a pinned section's scroll to land on, so the nav
  // lands on revealed content instead of the section's empty intro beat.
  { label: "How it works", href: "#how-it-works", enter: 0.075 },
  { label: "Mission control", href: "#mission-control", enter: 0 },
  { label: "Pricing", href: "#pricing", enter: 0 },
];

type LenisLike = { scroll: number; scrollTo: (t: number) => void };

function getLenis(): LenisLike | null {
  const raw = (window as unknown as { __lenis?: unknown }).__lenis;
  if (
    raw &&
    typeof raw === "object" &&
    typeof (raw as LenisLike).scrollTo === "function" &&
    typeof (raw as LenisLike).scroll === "number"
  ) {
    return raw as LenisLike;
  }
  return null;
}

function scrollToSection(href: string, enter: number) {
  const el = document.getElementById(href.slice(1));
  if (!el) return;
  const lenis = getLenis();
  const current = lenis ? lenis.scroll : window.scrollY;
  const top = el.getBoundingClientRect().top + current;
  const target = top + enter * Math.max(0, el.offsetHeight - window.innerHeight);
  if (lenis) lenis.scrollTo(target);
  else window.scrollTo({ top: target, behavior: "smooth" });
}

export default function Nav() {
  const navRef = useRef<HTMLElement>(null);
  const [scrolled, setScrolled] = useState(false);
  const mobile = useLayoutMobile();
  const [tight, setTight] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia(LAYOUT_TIGHT_MQ);
    const sync = () => setTight(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    gsap.fromTo(
      navRef.current,
      { opacity: 0, y: -20 },
      { opacity: 1, y: 0, duration: 0.8, ease: "power3.out", delay: 0.2 }
    );
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const padX = tight ? 12 : mobile ? 16 : 32;
  const ctaPad = tight ? "8px 12px" : "9px 20px";
  const connectLabel = tight ? "Connect" : "Connect →";

  return (
    <nav
      ref={navRef}
      className="orqis-nav"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 100,
        height: 60,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: `0 ${padX}px`,
        gap: mobile ? 8 : 12,
        backgroundColor: scrolled ? "rgba(0,0,0,0.88)" : "transparent",
        backdropFilter: scrolled ? "blur(24px)" : "none",
        borderBottom: scrolled ? `1px solid ${colors.border}` : "1px solid transparent",
        transition: "background-color 0.3s ease, border-color 0.3s ease",
      }}
    >
      <Link to="/" style={{ display: "flex", alignItems: "center", gap: 12, textDecoration: "none", flexShrink: 0 }}>
        <span style={{ fontFamily: fonts.anton, fontSize: tight ? 18 : 20, color: colors.white, letterSpacing: "0.06em" }}>
          ORQIS
        </span>
        <MetaLabel accent={colors.dimmer} style={{ display: "none" }}>
          (AGENT_OPS)
        </MetaLabel>
      </Link>

      {/* Desktop-only links (≥901px) — aligned with layout breakpoint, not Tailwind lg/1024 */}
      <div className="orqis-nav-links" style={{ display: mobile ? "none" : "flex", alignItems: "center", gap: 4 }}>
        {LINKS.map((l) => (
          <a
            key={l.label}
            href={l.href}
            onClick={(e) => {
              e.preventDefault();
              scrollToSection(l.href, l.enter);
            }}
            style={{
              padding: "6px 14px",
              fontSize: 11,
              color: colors.muted,
              textDecoration: "none",
              fontFamily: fonts.mono,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              transition: "color 0.2s",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = colors.ivory)}
            onMouseLeave={(e) => (e.currentTarget.style.color = colors.muted)}
          >
            {l.label}
          </a>
        ))}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: tight ? 6 : 10, flexShrink: 0 }}>
        <Link
          to="/dashboard"
          className="orqis-nav-cta"
          style={{
            padding: ctaPad,
            fontSize: 11,
            color: colors.green,
            textDecoration: "none",
            fontFamily: fonts.mono,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            border: `1px solid ${colors.green}33`,
            display: "inline-flex",
            alignItems: "center",
            whiteSpace: "nowrap",
          }}
        >
          {tight ? "Dash" : "Dashboard"}
        </Link>
        <Link
          to="/settings"
          className="btn-ghost orqis-nav-cta"
          style={{
            padding: ctaPad,
            fontSize: 11,
            textDecoration: "none",
            display: "inline-flex",
            alignItems: "center",
            whiteSpace: "nowrap",
          }}
        >
          {connectLabel}
        </Link>
      </div>
    </nav>
  );
}
