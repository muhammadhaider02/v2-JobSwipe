'use client';

import { motion } from 'motion/react';
import { Upload, TrendingUp, Sparkles, Briefcase } from 'lucide-react';

const steps = [
  {
    icon: Upload,
    title: 'Upload Your Resume',
    description:
      'AI extracts your skills, experience, and qualifications in seconds.',
  },
  {
    icon: TrendingUp,
    title: 'Get Market Ready',
    description:
      'Identify skill gaps, take AI quizzes, and learn from curated resources to sharpen your profile.',
  },
  {
    icon: Sparkles,
    title: 'Swipe on Jobs',
    description:
      'Like Tinder, but for your career. Swipe right on jobs you love.',
  },
  {
    icon: Briefcase,
    title: 'Land the Job',
    description:
      'AI optimizes your resume, writes a cover letter, and applies automatically.',
  },
];

const spring = { type: 'spring' as const, damping: 25, stiffness: 120 };

export function HowItWorks() {
  return (
    <section id="how-it-works" className="w-full py-16 md:py-32 dot-grid">
      <div className="max-w-6xl mx-auto px-6">
        <motion.div
          className="text-center mb-10 md:mb-20"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={spring}
        >
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold mb-4">
            How It Works
          </h2>
          <p className="text-muted-foreground text-lg max-w-xl mx-auto">
            Four simple steps from resume to dream job.
          </p>
        </motion.div>

        <div className="relative">
          <svg
            className="absolute top-12 left-0 w-full h-1 hidden md:block"
            viewBox="0 0 1000 4"
            preserveAspectRatio="none"
          >
            <motion.line
              x1="125"
              y1="2"
              x2="875"
              y2="2"
              stroke="currentColor"
              strokeWidth="2"
              strokeDasharray="6 6"
              className="text-border"
              initial={{ pathLength: 0 }}
              whileInView={{ pathLength: 1 }}
              viewport={{ once: true, amount: 0.5 }}
              transition={{ duration: 1.2, ease: 'easeInOut', delay: 0.3 }}
            />
          </svg>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-8 md:gap-8">
            {steps.map((step, i) => (
              <motion.div
                key={i}
                className="relative flex flex-col items-center text-center gap-4"
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.3 }}
                transition={{ ...spring, delay: i * 0.2 }}
              >
                <div className="relative z-10 w-24 h-24 rounded-2xl bg-primary/10 flex items-center justify-center">
                  <step.icon className="w-10 h-10 text-primary" />
                  <span className="absolute -top-2 -right-2 w-7 h-7 rounded-full bg-primary text-primary-foreground text-xs font-bold flex items-center justify-center">
                    {i + 1}
                  </span>
                </div>
                <h3 className="text-xl font-semibold">{step.title}</h3>
                <p className="text-muted-foreground max-w-xs">
                  {step.description}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
