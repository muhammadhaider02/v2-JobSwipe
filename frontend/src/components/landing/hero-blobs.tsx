'use client';

import { motion } from 'motion/react';
import { useTheme } from 'next-themes';
import { useEffect, useState } from 'react';

const blobConfigs = [
  {
    size: 'w-[500px] h-[500px] md:w-[700px] md:h-[700px]',
    position: '-top-32 -left-32',
    light: 'from-blue-400/30 to-purple-400/20',
    dark: 'from-blue-600/20 to-purple-600/15',
    duration: 20,
    delay: 0,
  },
  {
    size: 'w-[400px] h-[400px] md:w-[600px] md:h-[600px]',
    position: 'top-1/4 -right-32',
    light: 'from-purple-400/25 to-teal-400/20',
    dark: 'from-purple-600/15 to-teal-600/10',
    duration: 25,
    delay: 2,
  },
  {
    size: 'w-[350px] h-[350px] md:w-[500px] md:h-[500px]',
    position: 'bottom-0 left-1/4',
    light: 'from-teal-400/20 to-blue-400/25',
    dark: 'from-teal-600/10 to-blue-600/15',
    duration: 22,
    delay: 4,
  },
];

export function HeroBlobs() {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    setMounted(true);
    setReducedMotion(
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    );
  }, []);

  if (!mounted) return null;

  if (reducedMotion) {
    return (
      <div className="absolute inset-0 z-0 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-400/10 via-purple-400/10 to-teal-400/10 dark:from-blue-600/5 dark:via-purple-600/5 dark:to-teal-600/5" />
      </div>
    );
  }

  const isDark = resolvedTheme === 'dark';

  return (
    <div
      className={`absolute inset-0 z-0 overflow-hidden ${isDark ? 'mix-blend-screen' : 'mix-blend-multiply'}`}
    >
      {blobConfigs.map((blob, i) => (
        <motion.div
          key={i}
          className={`absolute ${blob.size} ${blob.position} rounded-full bg-gradient-to-br ${isDark ? blob.dark : blob.light} blur-[80px] md:blur-[100px]`}
          animate={{
            x: [0, 30, -20, 10, 0],
            y: [0, -20, 30, -10, 0],
            scale: [1, 1.1, 0.95, 1.05, 1],
          }}
          transition={{
            duration: blob.duration,
            repeat: Infinity,
            ease: 'easeInOut',
            delay: blob.delay,
          }}
          style={{ willChange: 'transform' }}
        />
      ))}
    </div>
  );
}
