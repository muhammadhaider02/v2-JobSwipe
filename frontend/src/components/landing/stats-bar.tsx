'use client';

import { motion, useMotionValue, useTransform, animate } from 'motion/react';
import { useEffect, useRef, useState } from 'react';

const stats = [
  { value: 10000, suffix: '+', label: 'Resumes Analyzed' },
  { value: 95, suffix: '%', label: 'Match Accuracy' },
  { value: 3, suffix: 'x', label: 'Faster Applications' },
];

function AnimatedCounter({
  target,
  suffix,
}: {
  target: number;
  suffix: string;
}) {
  const count = useMotionValue(0);
  const rounded = useTransform(count, (v) => {
    if (target >= 1000) return Math.round(v).toLocaleString();
    return Math.round(v).toString();
  });
  const [inView, setInView] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setInView(true);
      },
      { threshold: 0.5 }
    );
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!inView) return;
    const controls = animate(count, target, {
      duration: 2,
      ease: 'easeOut',
    });
    return controls.stop;
  }, [inView, count, target]);

  return (
    <span ref={ref} className="tabular-nums">
      <motion.span>{rounded}</motion.span>
      {suffix}
    </span>
  );
}

export function StatsBar() {
  return (
    <section className="w-full border-y border-border bg-muted/50">
      <div className="max-w-6xl mx-auto px-6 py-12 md:py-16">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-12">
          {stats.map((stat, i) => (
            <motion.div
              key={i}
              className="flex flex-col items-center text-center gap-2"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.5 }}
              transition={{
                type: 'spring',
                damping: 25,
                stiffness: 120,
                delay: i * 0.15,
              }}
            >
              <span className="text-4xl md:text-5xl font-bold text-foreground">
                <AnimatedCounter target={stat.value} suffix={stat.suffix} />
              </span>
              <span className="text-muted-foreground text-sm md:text-base">
                {stat.label}
              </span>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
