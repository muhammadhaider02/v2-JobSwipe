import { HeroSection } from '@/components/landing/hero-section';
import { StatsBar } from '@/components/landing/stats-bar';
import { HowItWorks } from '@/components/landing/how-it-works';
import { FeatureResume } from '@/components/landing/feature-resume';
import { FeatureSwipe } from '@/components/landing/feature-swipe';
import { FeatureAutoApply } from '@/components/landing/feature-auto-apply';
import { FeatureSkills } from '@/components/landing/feature-skills';
import { CTASection } from '@/components/landing/cta-section';
import { LandingFooter } from '@/components/landing/landing-footer';

export default function HomePage() {
  return (
    <>
      <HeroSection />
      <StatsBar />
      <HowItWorks />
      <FeatureResume />
      <FeatureSwipe />
      <FeatureAutoApply />
      <FeatureSkills />
      <CTASection />
      <LandingFooter />
    </>
  );
}
