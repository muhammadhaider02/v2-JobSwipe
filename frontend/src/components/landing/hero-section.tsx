'use client';

import { motion, useScroll, useTransform } from 'motion/react';
import { useRef } from 'react';
import Link from 'next/link';
import {
  Sparkles,
  CheckCircle,
  FileText,
  Target,
  BrainCircuit,
  ShieldCheck,
} from 'lucide-react';
import dynamic from 'next/dynamic';

const HeroBlobs = dynamic(
  () => import('./hero-blobs').then((m) => ({ default: m.HeroBlobs })),
  { ssr: false }
);

const spring = { type: 'spring' as const, damping: 25, stiffness: 120 };

const floatingCards = [
  {
    icon: Sparkles,
    text: '98% Match',
    color: 'text-green-500',
    pos: 'top-[15%] left-[4%] md:left-[7%]',
    delay: 0.8,
    yOffset: -15,
  },
  {
    icon: FileText,
    text: 'Resume Optimized',
    color: 'text-blue-500',
    pos: 'top-[28%] right-[3%] md:right-[6%]',
    delay: 1.0,
    yOffset: 20,
  },
  {
    icon: CheckCircle,
    text: 'Applied Successfully',
    color: 'text-emerald-500',
    pos: 'bottom-[28%] left-[6%] md:left-[10%]',
    delay: 1.2,
    yOffset: -10,
  },
  {
    icon: Target,
    text: '5 Roles Matched',
    color: 'text-violet-500',
    pos: 'bottom-[18%] right-[4%] md:right-[9%]',
    delay: 1.35,
    yOffset: 15,
  },
  {
    icon: BrainCircuit,
    text: 'Skills Extracted',
    color: 'text-amber-500',
    pos: 'top-[50%] left-[2%] md:left-[5%]',
    delay: 1.5,
    yOffset: -12,
  },
  {
    icon: ShieldCheck,
    text: 'Cover Letter Ready',
    color: 'text-teal-500',
    pos: 'top-[55%] right-[2%] md:right-[5%]',
    delay: 1.65,
    yOffset: 18,
  },
];

export function HeroSection() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start start', 'end start'],
  });

  const heroOpacity = useTransform(scrollYProgress, [0, 0.8], [1, 0]);
  const heroY = useTransform(scrollYProgress, [0, 0.8], [0, -60]);

  return (
    <section
      ref={ref}
      className="relative min-h-screen w-full flex items-center justify-center overflow-hidden"
    >
      <HeroBlobs />

      <motion.div
        style={{ opacity: heroOpacity, y: heroY }}
        className="relative z-10 flex flex-col items-center text-center px-6 max-w-4xl mx-auto gap-6"
      >
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...spring, delay: 0.1 }}
        >
          <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium glass text-foreground/80">
            <Sparkles className="w-4 h-4 text-primary" />
            AI-Powered Career Platform
          </span>
        </motion.div>

        <motion.h1
          className="text-4xl sm:text-5xl md:text-7xl lg:text-8xl font-bold tracking-tight leading-[1.1]"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...spring, delay: 0.25 }}
        >
          Apply Less,
          <br />
          <span className="text-gradient">Land More.</span>
        </motion.h1>

        <motion.p
          className="text-lg sm:text-xl text-muted-foreground max-w-2xl"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...spring, delay: 0.4 }}
        >
          Upload your resume. Swipe on jobs. Let AI optimize your application
          and apply automatically.
        </motion.p>

        <motion.div
          className="flex flex-col sm:flex-row gap-4 mt-2"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...spring, delay: 0.55 }}
        >
          <Link
            href="/auth/sign-up"
            className="relative inline-flex items-center justify-center rounded-xl text-base font-semibold bg-primary text-primary-foreground hover:bg-primary/90 h-12 px-8 transition-all shimmer glow-primary hover:scale-105 w-full sm:w-auto"
          >
            Get Started Free
          </Link>
          <a
            href="#how-it-works"
            className="inline-flex items-center justify-center rounded-xl text-base font-semibold border border-border bg-background/50 hover:bg-accent hover:text-accent-foreground h-12 px-8 transition-all backdrop-blur-sm hover:scale-105 w-full sm:w-auto"
          >
            See How It Works
          </a>
        </motion.div>
      </motion.div>

      {floatingCards.map((card, i) => (
        <motion.div
          key={i}
          className={`absolute ${card.pos} hidden md:flex items-center gap-2 px-4 py-2.5 rounded-xl glass shadow-lg`}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ ...spring, delay: card.delay }}
          style={{
            y: useTransform(
              scrollYProgress,
              [0, 1],
              [0, card.yOffset * 3]
            ),
          }}
        >
          <card.icon className={`w-4 h-4 ${card.color}`} />
          <span className="text-sm font-medium whitespace-nowrap">
            {card.text}
          </span>
        </motion.div>
      ))}
    </section>
  );
}
