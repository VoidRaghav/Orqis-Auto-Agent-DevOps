import dynamic from "next/dynamic";
import Nav from "@/components/Nav";
import HeroSection from "@/components/HeroSection";
import TickerSection from "@/components/TickerSection";
import ScrollTextSection from "@/components/ScrollTextSection";
import FeaturesSection from "@/components/FeaturesSection";
import DashboardPreview from "@/components/DashboardPreview";
import AnalyticsSection from "@/components/AnalyticsSection";
import PricingSection from "@/components/PricingSection";
import FooterCTA from "@/components/FooterCTA";

const SmoothScrollProvider = dynamic(
  () => import("@/components/SmoothScrollProvider"),
  { ssr: false }
);

export default function Home() {
  return (
    <SmoothScrollProvider>
      <main className="relative" style={{ backgroundColor: "#000000", overflowX: "clip" }}>
        <Nav />
        <HeroSection />
        <TickerSection />
        <ScrollTextSection />
        <FeaturesSection />
        <DashboardPreview />
        <AnalyticsSection />
        <PricingSection />
        <FooterCTA />
      </main>
    </SmoothScrollProvider>
  );
}
