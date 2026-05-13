'use client';

import { motion, AnimatePresence } from 'motion/react';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { FormField } from './form-field';

interface Education {
  degree: string;
  institution: string;
  startYear: string;
  endYear: string;
  gpa: string;
}

interface StepEducationProps {
  education: Education[];
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

export function StepEducation({
  education,
  errors,
  onArrayInput,
  onAdd,
  onRemove,
}: StepEducationProps) {
  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="space-y-4"
    >
      <AnimatePresence mode="popLayout">
        {education.map((edu, index) => (
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
              <h3 className="text-sm font-semibold">Education {index + 1}</h3>
              {education.length > 1 && (
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
                label="Degree"
                id={`edu-degree-${index}`}
                required
                value={edu.degree}
                onChange={onArrayInput(index, 'degree')}
                error={index === 0 ? errors.degree : undefined}
              />
              <FormField
                label="Institution"
                id={`edu-institution-${index}`}
                required
                value={edu.institution}
                onChange={onArrayInput(index, 'institution')}
                error={index === 0 ? errors.institution : undefined}
              />
              <FormField
                label="Start Year"
                id={`edu-start-${index}`}
                value={edu.startYear}
                onChange={onArrayInput(index, 'startYear')}
                placeholder="2020"
              />
              <FormField
                label="End Year"
                id={`edu-end-${index}`}
                value={edu.endYear}
                onChange={onArrayInput(index, 'endYear')}
                placeholder="2024"
              />
              <div className="md:col-span-2">
                <FormField
                  label="GPA"
                  id={`edu-gpa-${index}`}
                  value={edu.gpa}
                  onChange={onArrayInput(index, 'gpa')}
                  placeholder="3.8 / 4.0"
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
          Add Education
        </Button>
      </motion.div>
    </motion.div>
  );
}
