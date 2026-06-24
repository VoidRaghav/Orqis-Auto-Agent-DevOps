import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import CinematicHero from "@/components/CinematicHero";
import { useRobotFlowOptional } from "@/components/RobotFlowContext";
import { measureHeroScrub } from "@/lib/flow-phase";

gsap.registerPlugin(ScrollTrigger);

export default function HeroSection() {
  const scrollWrapRef = useRef<HTMLDivElement>(null);
  const flow = useRobotFlowOptional();

  useEffect(() => {
    const wrap = scrollWrapRef.current;
    if (!wrap || !flow) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reducedMotion) {
      const sync = () => {
        flow.heroScrubRef.current = measureHeroScrub();
      };
      sync();
      window.addEventListener("scroll", sync, { passive: true });
      return () => window.removeEventListener("scroll", sync);
    }

    let st: ScrollTrigger | null = null;

    const mountTrigger = () => {
      flow.heroScrubRef.current = 0;
      st?.kill();
      ScrollTrigger.refresh();
      st = ScrollTrigger.create({
        trigger: wrap,
        scroller: document.body,
        start: "top top",
        end: "bottom bottom",
        scrub: 0.85,
        invalidateOnRefresh: true,
        onUpdate: (self) => {
          flow.heroScrubRef.current = self.progress;
        },
      });
      st.refresh();
      flow.heroScrubRef.current = st.progress;
    };

    const onSplashDone = () => {
      window.requestAnimationFrame(mountTrigger);
    };

    window.addEventListener("orqis:splash-done", onSplashDone);
    const boot = window.setTimeout(mountTrigger, 1600);

    return () => {
      window.clearTimeout(boot);
      window.removeEventListener("orqis:splash-done", onSplashDone);
      st?.kill();
    };
  }, [flow]);

  return (
    <div ref={scrollWrapRef} className="cinematic-hero-scroll">
      <section className="cinematic-hero-stage">
        <CinematicHero />
      </section>
    </div>
  );
}
