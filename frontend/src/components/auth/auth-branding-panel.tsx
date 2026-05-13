'use client';

import { motion } from 'motion/react';
import { useEffect, useState } from 'react';

const spring = { type: 'spring' as const, damping: 25, stiffness: 120 };

export function AuthBrandingPanel() {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    setReducedMotion(
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    );
  }, []);

  return (
    <div className="relative h-full w-full overflow-hidden bg-zinc-950 flex flex-col items-center justify-center p-12">
      <div className="absolute inset-0 dot-grid opacity-30" />

      {!reducedMotion && (
        <>
          <motion.div
            className="absolute w-[400px] h-[400px] rounded-full bg-gradient-to-br from-blue-600/15 to-purple-600/10 blur-[100px]"
            animate={{ x: [0, 20, -10, 0], y: [0, -15, 20, 0], scale: [1, 1.1, 0.95, 1] }}
            transition={{ duration: 20, repeat: Infinity, ease: 'easeInOut' }}
            style={{ top: '10%', left: '20%' }}
          />
          <motion.div
            className="absolute w-[300px] h-[300px] rounded-full bg-gradient-to-br from-teal-600/10 to-blue-600/15 blur-[80px]"
            animate={{ x: [0, -20, 15, 0], y: [0, 20, -10, 0], scale: [1, 0.95, 1.08, 1] }}
            transition={{ duration: 25, repeat: Infinity, ease: 'easeInOut', delay: 3 }}
            style={{ bottom: '15%', right: '15%' }}
          />
        </>
      )}

      <div className="relative z-10 flex flex-col items-center text-center gap-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...spring, delay: 0.1 }}
        >
          <h2 className="text-5xl md:text-6xl font-bold text-white tracking-tighter leading-none">
            JobSwipe
          </h2>
        </motion.div>
        <motion.p
          className="text-zinc-400 text-lg md:text-xl tracking-wide"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...spring, delay: 0.3 }}
        >
          Apply less, land more.
        </motion.p>
      </div>
    </div>
  );
}
