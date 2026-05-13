'use client';

import { motion, type Variant } from 'motion/react';
import { type ReactNode } from 'react';

type Direction = 'up' | 'down' | 'left' | 'right';

const offsets: Record<Direction, { x?: number; y?: number }> = {
  up: { y: 40 },
  down: { y: -40 },
  left: { x: -40 },
  right: { x: 40 },
};

export function ScrollReveal({
  children,
  direction = 'up',
  delay = 0,
  className,
}: {
  children: ReactNode;
  direction?: Direction;
  delay?: number;
  className?: string;
}) {
  const offset = offsets[direction];

  const hidden: Variant = { opacity: 0, ...offset };
  const visible: Variant = {
    opacity: 1,
    x: 0,
    y: 0,
    transition: {
      type: 'spring',
      damping: 25,
      stiffness: 120,
      delay,
    },
  };

  return (
    <motion.div
      initial={hidden}
      whileInView={visible}
      viewport={{ once: true, amount: 0.3 }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
