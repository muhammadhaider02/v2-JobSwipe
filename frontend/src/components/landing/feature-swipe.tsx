'use client';

import { motion, AnimatePresence } from 'motion/react';
import { MapPin, Building2, TrendingUp } from 'lucide-react';
import { useEffect, useState, useRef } from 'react';

const jobs = [
  {
    title: 'Senior Frontend Engineer',
    company: 'TechCorp',
    location: 'Remote',
    match: 98,
    skills: ['React', 'TypeScript', 'Next.js'],
  },
  {
    title: 'Full Stack Developer',
    company: 'StartupAI',
    location: 'San Francisco',
    match: 91,
    skills: ['Node.js', 'React', 'PostgreSQL'],
  },
  {
    title: 'Software Engineer II',
    company: 'CloudScale',
    location: 'New York',
    match: 87,
    skills: ['Python', 'AWS', 'Docker'],
  },
];

const spring = { type: 'spring' as const, damping: 25, stiffness: 120 };

export function FeatureSwipe() {
  const [current, setCurrent] = useState(0);
  const [swiping, setSwiping] = useState(false);
  const inView = useRef(false);
  const intervalRef = useRef<ReturnType<typeof setInterval>>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        inView.current = entry.isIntersecting;
      },
      { threshold: 0.3 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      if (!inView.current) return;
      setSwiping(true);
      setTimeout(() => {
        setCurrent((p) => (p + 1) % jobs.length);
        setSwiping(false);
      }, 600);
    }, 3500);
    return () => clearInterval(intervalRef.current);
  }, []);

  return (
    <section className="w-full py-24 md:py-32 bg-muted/30 dot-grid">
      <div className="max-w-6xl mx-auto px-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-20 items-center">
          <motion.div
            ref={containerRef}
            className="relative h-[360px] flex items-center justify-center order-2 lg:order-1"
            initial={{ opacity: 0, x: -40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ ...spring, delay: 0.2 }}
          >
            {[2, 1, 0].map((offset) => {
              const idx = (current + offset) % jobs.length;
              const job = jobs[idx];
              const isTop = offset === 0;

              return (
                <AnimatePresence key={`${current}-${offset}`}>
                  <motion.div
                    className="absolute w-full max-w-[320px] bg-card border border-border rounded-2xl p-6 shadow-lg"
                    style={{
                      zIndex: 3 - offset,
                    }}
                    initial={
                      isTop
                        ? { scale: 0.9, y: 10, opacity: 0 }
                        : { scale: 1 - offset * 0.05, y: offset * 12 }
                    }
                    animate={
                      isTop && swiping
                        ? {
                            x: 200,
                            rotate: 15,
                            opacity: 0,
                            transition: { duration: 0.5, ease: 'easeIn' },
                          }
                        : {
                            scale: 1 - offset * 0.05,
                            y: offset * 12,
                            opacity: 1 - offset * 0.15,
                            x: 0,
                            rotate: 0,
                          }
                    }
                    transition={{ ...spring, delay: isTop ? 0 : 0.1 }}
                  >
                    {isTop && !swiping && (
                      <div className="absolute -top-3 -right-3 px-3 py-1 rounded-full bg-green-500 text-white text-xs font-bold shadow-md">
                        MATCH
                      </div>
                    )}
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <h4 className="font-semibold text-base">
                          {job.title}
                        </h4>
                        <div className="flex items-center gap-1.5 text-muted-foreground text-sm mt-1">
                          <Building2 className="w-3.5 h-3.5" />
                          {job.company}
                        </div>
                        <div className="flex items-center gap-1.5 text-muted-foreground text-sm mt-0.5">
                          <MapPin className="w-3.5 h-3.5" />
                          {job.location}
                        </div>
                      </div>
                      <div className="flex items-center gap-1 text-green-500">
                        <TrendingUp className="w-4 h-4" />
                        <span className="text-lg font-bold">{job.match}%</span>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {job.skills.map((s) => (
                        <span
                          key={s}
                          className="px-2 py-0.5 rounded-md bg-primary/10 text-primary text-xs font-medium"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  </motion.div>
                </AnimatePresence>
              );
            })}
          </motion.div>

          <motion.div
            className="order-1 lg:order-2"
            initial={{ opacity: 0, x: 40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={spring}
          >
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-sm font-medium mb-4">
              <TrendingUp className="w-3.5 h-3.5" />
              Smart Matching
            </div>
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold mb-6">
              Swipe Right on{' '}
              <span className="text-gradient">Your Future</span>
            </h2>
            <p className="text-muted-foreground text-lg mb-6 max-w-lg">
              AI ranks every job by how well it matches your skills, experience,
              and preferences. See your match percentage at a glance, then
              swipe to apply.
            </p>
            <ul className="space-y-3 text-muted-foreground">
              {[
                'Jobs scored across 5 weighted factors',
                'Skill overlap, location, and experience matching',
                'One swipe to start your application',
              ].map((item, i) => (
                <motion.li
                  key={i}
                  className="flex items-center gap-3"
                  initial={{ opacity: 0, x: 20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ ...spring, delay: 0.3 + i * 0.1 }}
                >
                  <div className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                  {item}
                </motion.li>
              ))}
            </ul>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
