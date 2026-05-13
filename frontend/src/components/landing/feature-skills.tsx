'use client';

import { motion } from 'motion/react';
import { BookOpen, Target, TrendingUp } from 'lucide-react';

const skillBars = [
  { name: 'React', level: 92, color: 'from-blue-500 to-blue-600' },
  { name: 'TypeScript', level: 85, color: 'from-blue-600 to-indigo-600' },
  { name: 'Python', level: 68, color: 'from-green-500 to-emerald-600' },
  { name: 'System Design', level: 45, gap: true, color: 'from-orange-500 to-amber-500' },
  { name: 'AWS', level: 38, gap: true, color: 'from-orange-500 to-red-500' },
];

const resources = [
  { type: 'Video', title: 'AWS Fundamentals', source: 'YouTube' },
  { type: 'Course', title: 'System Design Interview', source: 'Online' },
  { type: 'Article', title: 'Cloud Architecture Patterns', source: 'Blog' },
];

const spring = { type: 'spring' as const, damping: 25, stiffness: 120 };

export function FeatureSkills() {
  return (
    <section className="w-full py-24 md:py-32 bg-muted/30 dot-grid">
      <div className="max-w-6xl mx-auto px-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-20 items-center">
          <motion.div
            className="order-2 lg:order-1 space-y-6"
            initial={{ opacity: 0, x: -40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ ...spring, delay: 0.2 }}
          >
            <div className="bg-card border border-border rounded-2xl p-6 shadow-xl">
              <div className="flex items-center gap-3 mb-5 pb-4 border-b border-border">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Target className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <p className="font-semibold text-sm">Skill Analysis</p>
                  <p className="text-xs text-muted-foreground">
                    For: Senior Frontend Engineer
                  </p>
                </div>
              </div>

              <div className="space-y-4">
                {skillBars.map((skill, i) => (
                  <div key={skill.name}>
                    <div className="flex items-center justify-between text-sm mb-1.5">
                      <span className="font-medium flex items-center gap-2">
                        {skill.name}
                        {skill.gap && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-500 font-semibold">
                            GAP
                          </span>
                        )}
                      </span>
                      <span className="text-muted-foreground tabular-nums">
                        {skill.level}%
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-muted overflow-hidden">
                      <motion.div
                        className={`h-full rounded-full bg-gradient-to-r ${skill.color}`}
                        initial={{ width: '0%' }}
                        whileInView={{ width: `${skill.level}%` }}
                        viewport={{ once: true }}
                        transition={{
                          duration: 1.2,
                          ease: 'easeOut',
                          delay: 0.4 + i * 0.12,
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-card border border-border rounded-2xl p-5 shadow-lg">
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-3 font-medium">
                Recommended Resources
              </p>
              <div className="space-y-2.5">
                {resources.map((res, i) => (
                  <motion.div
                    key={i}
                    className="flex items-center gap-3 p-2.5 rounded-lg bg-muted/50"
                    initial={{ opacity: 0, y: 10 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ ...spring, delay: 1 + i * 0.1 }}
                  >
                    <div className="w-8 h-8 rounded-md bg-primary/10 flex items-center justify-center shrink-0">
                      <BookOpen className="w-4 h-4 text-primary" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">
                        {res.title}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {res.type} &middot; {res.source}
                      </p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
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
              Growth Engine
            </div>
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold mb-6">
              Don&apos;t Just Find Jobs,{' '}
              <span className="text-gradient">Grow Into Them</span>
            </h2>
            <p className="text-muted-foreground text-lg mb-6 max-w-lg">
              See exactly which skills you&apos;re missing for your dream role.
              Get curated learning resources like videos, articles, and courses,
              personalized to fill your gaps.
            </p>
            <ul className="space-y-3 text-muted-foreground">
              {[
                'Skill gap detection for each target role',
                'Curated YouTube, articles, and courses',
                'Verify skills with AI-generated quizzes',
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
