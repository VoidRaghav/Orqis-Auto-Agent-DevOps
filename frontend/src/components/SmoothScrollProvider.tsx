"use client";

import { useEffect, useRef } from "react";
import Lenis from "lenis";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { LAYOUT_MOBILE_MQ, isLayoutMobile } from "@/lib/layout-breakpoint";

gsap.registerPlugin(ScrollTrigger);

/** Keep Lenis always — destroy breaks HeroSection ScrollTrigger scrollerProxy. */
export default function SmoothScrollProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const lenisRef = useRef<Lenis | null>(null);

  useEffect(() => {
    const mobile = isLayoutMobile();
    const lenis = new Lenis({
      duration: mobile ? 0.85 : 1.05,
      easing: (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
      wheelMultiplier: 0.9,
      touchMultiplier: mobile ? 1.35 : 2,
      autoRaf: false,
      lerp: mobile ? 0.12 : 0.085,
    });

    lenisRef.current = lenis;
    // Expose the instance so in-page anchors (Nav) can scroll through Lenis
    // instead of fighting it with native window.scrollTo.
    (window as unknown as { __lenis?: Lenis }).__lenis = lenis;

    const baseDuration = mobile ? 0.85 : 1.05;
    const baseLerp = mobile ? 0.12 : 0.085;

    lenis.on("scroll", (e: { velocity: number }) => {
      ScrollTrigger.update();
      const v = Math.abs(e.velocity);
      lenis.options.duration = baseDuration + Math.min(0.4, v * 0.012);
      lenis.options.lerp = baseLerp + Math.min(0.04, v * 0.0015);
    });

    ScrollTrigger.scrollerProxy(document.body, {
      scrollTop(value) {
        if (arguments.length && value !== undefined) {
          lenis.scrollTo(value, { immediate: true });
        }
        return lenis.scroll;
      },
      getBoundingClientRect() {
        return {
          top: 0,
          left: 0,
          width: window.innerWidth,
          height: window.innerHeight,
        };
      },
      pinType: document.body.style.transform ? "transform" : "fixed",
    });

    const onRefresh = () => lenis.resize();
    ScrollTrigger.addEventListener("refresh", onRefresh);

    // Drive Lenis via GSAP ticker (single RAF loop)
    const tickerFn = (time: number) => {
      lenis.raf(time * 1000);
    };
    gsap.ticker.add(tickerFn);
    gsap.ticker.lagSmoothing(0);

    // Retune touch feel when crossing layout breakpoint; never destroy Lenis
    const mq = window.matchMedia(LAYOUT_MOBILE_MQ);
    const applyMobileOpts = (isMob: boolean) => {
      lenis.options.touchMultiplier = isMob ? 1.35 : 2;
      lenis.options.duration = isMob ? 0.85 : 1.05;
      lenis.options.lerp = isMob ? 0.12 : 0.085;
    };
    const onMq = () => {
      applyMobileOpts(mq.matches);
      lenis.resize();
      ScrollTrigger.refresh();
    };
    mq.addEventListener("change", onMq);

    const onResize = () => {
      lenis.resize();
      ScrollTrigger.refresh();
    };
    window.addEventListener("resize", onResize, { passive: true });
    window.addEventListener("orientationchange", onResize, { passive: true });

    // Refresh ScrollTrigger after layout settles
    const rafId = requestAnimationFrame(() => {
      ScrollTrigger.refresh();
    });

    return () => {
      cancelAnimationFrame(rafId);
      mq.removeEventListener("change", onMq);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("orientationchange", onResize);
      ScrollTrigger.removeEventListener("refresh", onRefresh);
      ScrollTrigger.scrollerProxy(document.body, {});
      lenis.destroy();
      delete (window as unknown as { __lenis?: Lenis }).__lenis;
      gsap.ticker.remove(tickerFn);
    };
  }, []);

  return <>{children}</>;
}
