'use client';

import { motion, AnimatePresence } from 'motion/react';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { FormField } from './form-field';

interface Project {
  name: string;
  description: string;
  link: string;
}

interface StepProjectsProps {
  projects: Project[];
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

export function StepProjects({
  projects,
  onArrayInput,
  onAdd,
  onRemove,
}: StepProjectsProps) {
  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="space-y-4"
    >
      <AnimatePresence mode="popLayout">
        {projects.map((proj, index) => (
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
              <h3 className="text-sm font-semibold">Project {index + 1}</h3>
              {projects.length > 1 && (
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
                label="Project Name"
                id={`proj-name-${index}`}
                value={proj.name}
                onChange={onArrayInput(index, 'name')}
              />
              <FormField
                label="Link"
                id={`proj-link-${index}`}
                value={proj.link}
                onChange={onArrayInput(index, 'link')}
                placeholder="https://github.com/..."
              />
              <div className="md:col-span-2">
                <FormField
                  label="Description"
                  id={`proj-desc-${index}`}
                  multiline
                  value={proj.description}
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
          Add Project
        </Button>
      </motion.div>
    </motion.div>
  );
}
