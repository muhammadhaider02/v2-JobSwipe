'use client';

import { motion } from 'motion/react';
import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Step {
  id: number;
  label: string;
}

interface StepIndicatorProps {
  steps: Step[];
  currentStep: number;
  maxVisitedStep: number;
  onJump: (to: number) => void;
}

export function StepIndicator({
  steps,
  currentStep,
  maxVisitedStep,
  onJump,
}: StepIndicatorProps) {
  const progress = ((currentStep + 1) / steps.length) * 100;

  return (
    <div className="w-full">
      <div className="hidden md:flex items-center justify-between gap-1 mb-6">
        {steps.map((step, idx) => {
          const isActive = idx === currentStep;
          const isCompleted = idx < currentStep;
          const isAccessible = idx <= maxVisitedStep;

          return (
            <div key={step.id} className="flex items-center flex-1 last:flex-initial">
              <button
                onClick={() => onJump(idx)}
                disabled={!isAccessible}
                className={cn(
                  'relative flex items-center gap-2 group',
                  !isAccessible && 'cursor-not-allowed',
                )}
              >
                <motion.div
                  className={cn(
                    'w-9 h-9 rounded-full flex items-center justify-center text-sm font-medium border-2 transition-colors',
                    isActive &&
                      'bg-primary border-primary text-primary-foreground',
                    isCompleted &&
                      'bg-primary/10 border-primary text-primary',
                    !isActive &&
                      !isCompleted &&
                      isAccessible &&
                      'border-border text-muted-foreground hover:border-primary/50',
                    !isAccessible &&
                      'border-border/50 text-muted-foreground/50',
                  )}
                  whileTap={isAccessible ? { scale: 0.92 } : undefined}
                >
                  {isCompleted ? (
                    <Check className="w-4 h-4" />
                  ) : (
                    step.id
                  )}
                </motion.div>
                <span
                  className={cn(
                    'text-sm font-medium hidden lg:block',
                    isActive && 'text-foreground',
                    isCompleted && 'text-foreground/70',
                    !isActive &&
                      !isCompleted &&
                      'text-muted-foreground',
                  )}
                >
                  {step.label}
                </span>
              </button>
              {idx < steps.length - 1 && (
                <div className="flex-1 mx-3 h-px bg-border relative overflow-hidden">
                  <motion.div
                    className="absolute inset-y-0 left-0 bg-primary"
                    initial={{ width: '0%' }}
                    animate={{
                      width: isCompleted ? '100%' : '0%',
                    }}
                    transition={{
                      type: 'spring',
                      stiffness: 100,
                      damping: 20,
                    }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="md:hidden mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-muted-foreground">
            Step {currentStep + 1} of {steps.length}
          </span>
          <span className="text-sm font-semibold">
            {steps[currentStep].label}
          </span>
        </div>
        <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-primary rounded-full"
            animate={{ width: `${progress}%` }}
            transition={{
              type: 'spring',
              stiffness: 100,
              damping: 20,
            }}
          />
        </div>
      </div>
    </div>
  );
}
