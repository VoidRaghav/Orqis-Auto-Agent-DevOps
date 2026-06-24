import SmoothScrollProvider from "@/components/SmoothScrollProvider";
import Nav from "@/components/Nav";
import HeroSection from "@/components/HeroSection";
import TickerSection from "@/components/TickerSection";
import FlowZone from "@/components/FlowZone";
import ScrollTextSection from "@/components/ScrollTextSection";
import FeaturesSection from "@/components/FeaturesSection";
import MissionControlCinematic from "@/components/MissionControlCinematic";
import AnalyticsSection from "@/components/AnalyticsSection";
import PricingSection from "@/components/PricingSection";
import FooterCTA from "@/components/FooterCTA";

export default function Home() {
  return (
    <SmoothScrollProvider>
      <main className="relative" style={{ backgroundColor: "#050a08", overflowX: "clip" }}>
        <Nav />
        <FlowZone>
          <HeroSection />
          <TickerSection />
          <ScrollTextSection />
          <div id="how-it-works">
            <FeaturesSection />
          </div>
          <MissionControlCinematic />
          <AnalyticsSection />
          <div id="pricing">
            <PricingSection />
          </div>
          <FooterCTA />
        </FlowZone>
      </main>
    </SmoothScrollProvider>
  );
}
