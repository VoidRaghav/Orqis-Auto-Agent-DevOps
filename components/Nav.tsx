"use client";

import { useEffect, useRef, useState } from "react";
import { gsap } from "gsap";

export default function Nav() {
  const navRef = useRef<HTMLElement>(null);
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    gsap.fromTo(navRef.current,
      { opacity: 0, y: -20 },
      { opacity: 1, y: 0, duration: 0.8, ease: "power3.out", delay: 0.2 }
    );
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const links = ["Product", "Docs", "Pricing", "Blog"];

  return (
    <nav
      ref={navRef}
      style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
        height: 60,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0 32px",
        backgroundColor: scrolled ? "rgba(0,0,0,0.85)" : "transparent",
        backdropFilter: scrolled ? "blur(20px)" : "none",
        borderBottom: scrolled ? "1px solid rgba(255,255,255,0.06)" : "1px solid transparent",
        transition: "background-color 0.3s ease, border-color 0.3s ease, backdrop-filter 0.3s ease",
      }}
    >
      {/* Logo */}
      <a href="#" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}>
        <div style={{
          width: 28, height: 28, borderRadius: 7,
          background: "linear-gradient(135deg, #ffffff 0%, #a0a0a0 100%)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 13, fontWeight: 700, color: "#000",
        }}>
          ⌬
        </div>
        <span style={{
          fontFamily: "'Anton', sans-serif", fontSize: 18,
          color: "#ffffff", letterSpacing: "0.02em",
        }}>
          ORQIS
        </span>
      </a>

      {/* Desktop links */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }} className="hidden lg:flex">
        {links.map((l) => (
          <a key={l} href="#" style={{
            padding: "6px 14px", fontSize: 13, fontWeight: 500,
            color: "#a0a0a0", textDecoration: "none",
            fontFamily: "'Inter', sans-serif",
            transition: "color 0.2s",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "#ffffff")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "#a0a0a0")}
          >
            {l}
          </a>
        ))}
      </div>

      {/* CTA */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <a href="#" style={{
          padding: "7px 16px", fontSize: 13, fontWeight: 500,
          color: "#a0a0a0", textDecoration: "none",
          fontFamily: "'Inter', sans-serif",
        }}>
          Sign In
        </a>
        <a href="#" className="btn-primary" style={{
          padding: "8px 20px", borderRadius: 8, fontSize: 13,
          textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 6,
        }}>
          Get Started
          <span style={{ fontSize: 11 }}>→</span>
        </a>
      </div>
    </nav>
  );
}
