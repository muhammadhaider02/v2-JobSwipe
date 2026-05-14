'use client';

import { motion } from 'motion/react';
import Link from 'next/link';
import { ArrowRight, Sparkles } from 'lucide-react';

const spring = { type: 'spring' as const, damping: 25, stiffness: 120 };

export function CTASection() {
  return (
    <section className="w-full py-16 md:py-32 relative overflow-hidden">
      <div className="absolute inset-0 dot-grid opacity-50" />

      <div className="relative z-10 max-w-3xl mx-auto px-6 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={spring}
          className="mb-5"
        >
          <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium bg-primary/10 text-primary">
            <Sparkles className="w-4 h-4" />
            Ready to get started?
          </span>
        </motion.div>

        <motion.h2
          className="text-4xl sm:text-5xl md:text-6xl font-bold mb-5"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ ...spring, delay: 0.1 }}
        >
          Your Next Job is{' '}
          <span className="text-gradient">One Swipe Away</span>
        </motion.h2>

        <motion.p
          className="text-lg text-muted-foreground mb-6 sm:mb-10 max-w-xl mx-auto"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ ...spring, delay: 0.2 }}
        >
          Join thousands of job seekers who stopped applying manually and
          started landing interviews.
        </motion.p>

        <motion.div
          className="flex flex-col sm:flex-row items-center justify-center gap-4"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ ...spring, delay: 0.3 }}
        >
          <Link
            href="/auth/sign-up"
            className="relative inline-flex items-center gap-2 rounded-xl text-base font-semibold bg-primary text-primary-foreground hover:bg-primary/90 h-12 px-8 transition-all shimmer glow-primary hover:scale-105"
          >
            Get Started Free
            <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            href="/auth/login"
            className="inline-flex items-center justify-center rounded-xl text-base font-semibold border border-border hover:bg-accent hover:text-accent-foreground h-12 px-8 transition-all hover:scale-105"
          >
            Sign In
          </Link>
        </motion.div>
      </div>
    </section>
  );
}
