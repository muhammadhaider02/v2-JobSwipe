'use client';

import { motion } from 'motion/react';
import { FileText, Zap } from 'lucide-react';

const skills = [
  'React',
  'TypeScript',
  'Node.js',
  'Python',
  'SQL',
  'AWS',
  'Docker',
  'Git',
];

const spring = { type: 'spring' as const, damping: 25, stiffness: 120 };

export function FeatureResume() {
  return (
    <section className="w-full py-24 md:py-32">
      <div className="max-w-6xl mx-auto px-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-20 items-center">
          <motion.div
            initial={{ opacity: 0, x: -40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={spring}
          >
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-sm font-medium mb-4">
              <Zap className="w-3.5 h-3.5" />
              AI-Powered
            </div>
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold mb-6">
              Your Resume,{' '}
              <span className="text-gradient">Understood</span>
            </h2>
            <p className="text-muted-foreground text-lg mb-6 max-w-lg">
              Upload any resume format. Our AI instantly extracts your skills,
              experience, and qualifications, building a complete profile in
              seconds.
            </p>
            <ul className="space-y-3 text-muted-foreground">
              {[
                'Supports PDF, DOCX, and plain text',
                'Extracts skills, roles, and experience levels',
                'Builds your candidate profile automatically',
              ].map((item, i) => (
                <motion.li
                  key={i}
                  className="flex items-center gap-3"
                  initial={{ opacity: 0, x: -20 }}
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

          <motion.div
            initial={{ opacity: 0, x: 40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ ...spring, delay: 0.2 }}
            className="relative"
          >
            <div className="relative bg-card border border-border rounded-2xl p-6 shadow-xl">
              <div className="flex items-center gap-3 mb-6 pb-4 border-b border-border">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <FileText className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <p className="font-semibold text-sm">resume_2024.pdf</p>
                  <p className="text-xs text-muted-foreground">
                    Analyzed in 2.3s
                  </p>
                </div>
              </div>

              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-3 font-medium">
                Extracted Skills
              </p>
              <div className="flex flex-wrap gap-2">
                {skills.map((skill, i) => (
                  <motion.span
                    key={skill}
                    className="px-3 py-1.5 rounded-lg bg-primary/10 text-primary text-sm font-medium"
                    initial={{ opacity: 0, scale: 0.5 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true }}
                    transition={{ ...spring, delay: 0.5 + i * 0.08 }}
                  >
                    {skill}
                  </motion.span>
                ))}
              </div>

              <div className="mt-6 pt-4 border-t border-border">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">
                    Profile Completeness
                  </span>
                  <span className="font-semibold text-green-500">94%</span>
                </div>
                <div className="mt-2 h-2 rounded-full bg-muted overflow-hidden">
                  <motion.div
                    className="h-full rounded-full bg-gradient-to-r from-primary to-green-500"
                    initial={{ width: '0%' }}
                    whileInView={{ width: '94%' }}
                    viewport={{ once: true }}
                    transition={{ duration: 1.5, ease: 'easeOut', delay: 0.8 }}
                  />
                </div>
              </div>
            </div>

            <div className="absolute -z-10 inset-0 bg-gradient-to-br from-primary/5 to-purple-500/5 rounded-2xl blur-xl scale-105" />
          </motion.div>
        </div>
      </div>
    </section>
  );
}
