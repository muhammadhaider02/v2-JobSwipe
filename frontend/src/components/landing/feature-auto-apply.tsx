'use client';

import { motion } from 'motion/react';
import { Bot, FileText, PenTool, Send, CheckCircle } from 'lucide-react';

const agentSteps = [
  {
    icon: FileText,
    label: 'Tailoring Resume',
    description: 'Optimizing for job requirements',
  },
  {
    icon: PenTool,
    label: 'Writing Cover Letter',
    description: 'Personalized to the role',
  },
  {
    icon: Send,
    label: 'Submitting Application',
    description: 'Auto-filling forms',
  },
  {
    icon: CheckCircle,
    label: 'Application Sent',
    description: 'Confirmation received',
  },
];

const spring = { type: 'spring' as const, damping: 25, stiffness: 120 };

export function FeatureAutoApply() {
  return (
    <section className="w-full py-16 md:py-32">
      <div className="max-w-6xl mx-auto px-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-20 items-center">
          <motion.div
            initial={{ opacity: 0, x: -40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={spring}
          >
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-sm font-medium mb-4">
              <Bot className="w-3.5 h-3.5" />
              AI Agents
            </div>
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold mb-6">
              One Swipe,{' '}
              <span className="text-gradient">Fully Applied</span>
            </h2>
            <p className="text-muted-foreground text-lg mb-6 max-w-lg">
              Our AI agents handle everything. They tailor your resume to the
              specific job, writing a personalized cover letter, and submitting
              the application. You just swipe.
            </p>
            <ul className="space-y-3 text-muted-foreground">
              {[
                'RAG-powered resume optimization per job',
                'LLM-generated personalized cover letters',
                'Automated form filling and submission',
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
            style={{ willChange: 'transform' }}
          >
            <div className="relative bg-card border border-border rounded-2xl p-6 shadow-xl">
              <div className="flex items-center gap-3 mb-6 pb-4 border-b border-border">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Bot className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <p className="font-semibold text-sm">Application Agent</p>
                  <p className="text-xs text-muted-foreground">
                    Processing your application...
                  </p>
                </div>
              </div>

              <div className="space-y-4">
                {agentSteps.map((step, i) => (
                  <motion.div
                    key={i}
                    className="flex items-center gap-4"
                    initial={{ opacity: 0, x: 20 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ ...spring, delay: 0.5 + i * 0.25 }}
                  >
                    <motion.div
                      className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
                        i === agentSteps.length - 1
                          ? 'bg-green-500/10'
                          : 'bg-primary/10'
                      }`}
                      initial={{ scale: 0 }}
                      whileInView={{ scale: 1 }}
                      viewport={{ once: true }}
                      transition={{ ...spring, delay: 0.6 + i * 0.25 }}
                    >
                      <step.icon
                        className={`w-4.5 h-4.5 ${
                          i === agentSteps.length - 1
                            ? 'text-green-500'
                            : 'text-primary'
                        }`}
                      />
                    </motion.div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium">{step.label}</p>
                      <p className="text-xs text-muted-foreground">
                        {step.description}
                      </p>
                    </div>
                    <motion.div
                      initial={{ opacity: 0, scale: 0 }}
                      whileInView={{ opacity: 1, scale: 1 }}
                      viewport={{ once: true }}
                      transition={{ ...spring, delay: 0.8 + i * 0.25 }}
                    >
                      <CheckCircle
                        className={`w-5 h-5 ${
                          i === agentSteps.length - 1
                            ? 'text-green-500'
                            : 'text-primary/60'
                        }`}
                      />
                    </motion.div>
                  </motion.div>
                ))}
              </div>
            </div>

            <div className="absolute -z-10 inset-0 bg-gradient-to-br from-primary/5 to-emerald-500/5 rounded-2xl blur-xl scale-105" />
          </motion.div>
        </div>
      </div>
    </section>
  );
}
