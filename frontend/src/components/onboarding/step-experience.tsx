'use client';

import { motion, AnimatePresence } from 'motion/react';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { FormField } from './form-field';

interface Experience {
  company: string;
  role: string;
  duration: string;
  description: string;
}

interface StepExperienceProps {
  experience: Experience[];
  errors: Record<string, string>;
  onArrayInput: (
    index: number,
    field: string,
  ) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
}

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};

const item = {
  hidden: { opacity: 0, y: 16 },
  show: {
    opacity: 1,
    y: 0,
    transition: { type: 'spring' as const, stiffness: 100, damping: 20 },
  },
  exit: { opacity: 0, y: -10, transition: { duration: 0.2 } },
};

export function StepExperience({
  experience,
  errors,
  onArrayInput,
  onAdd,
  onRemove,
}: StepExperienceProps) {
  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="space-y-4"
    >
      <AnimatePresence mode="popLayout">
        {experience.map((exp, index) => (
          <motion.div
            key={index}
            variants={item}
            initial="hidden"
            animate="show"
            exit="exit"
            layout
            className="border rounded-xl p-5 space-y-4"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">
                Experience {index + 1}
              </h3>
              {experience.length > 1 && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => onRemove(index)}
                  className="text-destructive hover:text-destructive hover:bg-destructive/10"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              )}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField
                label="Company"
                id={`exp-company-${index}`}
                required
                value={exp.company}
                onChange={onArrayInput(index, 'company')}
                error={index === 0 ? errors.company : undefined}
              />
              <FormField
                label="Role"
                id={`exp-role-${index}`}
                required
                value={exp.role}
                onChange={onArrayInput(index, 'role')}
                error={index === 0 ? errors.role : undefined}
              />
              <div className="md:col-span-2">
                <FormField
                  label="Duration"
                  id={`exp-duration-${index}`}
                  value={exp.duration}
                  onChange={onArrayInput(index, 'duration')}
                  placeholder="Jan 2022 - Present"
                />
              </div>
              <div className="md:col-span-2">
                <FormField
                  label="Description"
                  id={`exp-desc-${index}`}
                  multiline
                  value={exp.description}
                  onChange={onArrayInput(index, 'description')}
                />
              </div>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>

      <motion.div variants={item}>
        <Button
          type="button"
          variant="outline"
          onClick={onAdd}
          className="w-full border-dashed"
        >
          <Plus className="w-4 h-4" />
          Add Experience
        </Button>
      </motion.div>
    </motion.div>
  );
}
