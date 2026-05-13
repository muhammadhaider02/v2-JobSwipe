'use client';

import { motion, AnimatePresence } from 'motion/react';
import { X } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';

interface StepSkillsProps {
  skills: string[];
  errors: Record<string, string>;
  onKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  onRemove: (skill: string) => void;
}

const item = {
  hidden: { opacity: 0, scale: 0.8 },
  show: {
    opacity: 1,
    scale: 1,
    transition: { type: 'spring' as const, stiffness: 200, damping: 20 },
  },
  exit: { opacity: 0, scale: 0.8, transition: { duration: 0.15 } },
};

export function StepSkills({
  skills,
  errors,
  onKeyDown,
  onRemove,
}: StepSkillsProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 100, damping: 20 }}
      className="space-y-4"
    >
      <div className="grid gap-2">
        <Label htmlFor="skills-input">
          Skills <span className="text-destructive ml-0.5">*</span>
        </Label>
        <Input
          id="skills-input"
          placeholder="Type a skill and press Enter or comma"
          onKeyDown={onKeyDown}
          className={errors.skills ? 'border-destructive' : ''}
        />
        {errors.skills && (
          <p className="text-xs text-destructive">{errors.skills}</p>
        )}
        <p className="text-xs text-muted-foreground">
          You can also paste comma-separated skills.
        </p>
      </div>

      <div className="flex flex-wrap gap-2 min-h-[2.5rem]">
        <AnimatePresence mode="popLayout">
          {skills.map((skill) => (
            <motion.div
              key={skill}
              variants={item}
              initial="hidden"
              animate="show"
              exit="exit"
              layout
            >
              <Badge
                variant="secondary"
                className="gap-1.5 pr-1.5 cursor-default"
              >
                {skill}
                <button
                  type="button"
                  onClick={() => onRemove(skill)}
                  className="rounded-full p-0.5 hover:bg-foreground/10 transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              </Badge>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
