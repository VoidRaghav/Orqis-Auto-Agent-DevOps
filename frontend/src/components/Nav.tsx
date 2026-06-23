import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { gsap } from "gsap";
import MetaLabel from "@/components/ui/MetaLabel";
import { colors, fonts } from "@/lib/tokens";

const LINKS = [
  { label: "How it works", href: "#how-it-works" },
  { label: "Mission control", href: "#mission-control" },
  { label: "Pricing", href: "#pricing" },
];

export default function Nav() {
  const navRef = useRef<HTMLElement>(null);
  const [scrolled, setScrolled] = useState(false);

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

  return (
    <nav
      ref={navRef}
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
        padding: "0 32px",
        backgroundColor: scrolled ? "rgba(0,0,0,0.88)" : "transparent",
        backdropFilter: scrolled ? "blur(24px)" : "none",
        borderBottom: scrolled ? `1px solid ${colors.border}` : "1px solid transparent",
        transition: "background-color 0.3s ease, border-color 0.3s ease",
      }}
    >
      <Link to="/" style={{ display: "flex", alignItems: "center", gap: 12, textDecoration: "none" }}>
        <span style={{ fontFamily: fonts.anton, fontSize: 20, color: colors.white, letterSpacing: "0.06em" }}>
          ORQIS
        </span>
        <MetaLabel accent={colors.dimmer} style={{ display: "none" }}>
          (AGENT_OPS)
        </MetaLabel>
      </Link>

      <div style={{ display: "flex", alignItems: "center", gap: 4 }} className="hidden lg:flex">
        {LINKS.map((l) => (
          <a
            key={l.label}
            href={l.href}
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

      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <Link
          to="/dashboard"
          style={{
            padding: "7px 16px",
            fontSize: 10,
            color: colors.green,
            textDecoration: "none",
            fontFamily: fonts.mono,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            border: `1px solid ${colors.green}33`,
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <span
            className="pulse-slow"
            style={{ width: 5, height: 5, borderRadius: "50%", background: colors.green, display: "inline-block" }}
          />
          Dashboard
        </Link>
        <Link
          to="/settings"
          className="btn-ghost"
          style={{ padding: "8px 18px", textDecoration: "none", display: "inline-flex", alignItems: "center" }}
        >
          Connect →
        </Link>
      </div>
    </nav>
  );
}
