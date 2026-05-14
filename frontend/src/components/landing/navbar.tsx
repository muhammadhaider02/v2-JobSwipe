'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState, type ReactNode } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Menu, X } from 'lucide-react';

export function Navbar({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isLanding = pathname === '/';
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (!isLanding) return;
    const onScroll = () => setScrolled(window.scrollY > 80);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [isLanding]);

  useEffect(() => setMobileOpen(false), [pathname]);

  return (
    <nav
      className={
        isLanding
          ? `fixed top-0 left-0 w-full z-50 transition-all duration-300 ${
              scrolled || mobileOpen
                ? 'bg-background/80 backdrop-blur-md border-b border-b-foreground/10'
                : 'bg-transparent'
            }`
          : 'w-full flex border-b border-b-foreground/10 h-16 bg-background'
      }
    >
      <div className="w-full flex justify-between items-center p-3 px-6 text-sm h-16">
        <div className="flex gap-5 items-center font-semibold text-lg hover:text-primary transition-colors">
          <Link href={isLanding ? '/' : '/onboarding'}>JobSwipe</Link>
        </div>
        <div className="hidden md:flex">{children}</div>
        <button
          className="md:hidden flex items-center justify-center w-11 h-11 rounded-lg hover:bg-accent transition-colors"
          onClick={() => setMobileOpen((v) => !v)}
          aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            className="md:hidden absolute top-16 left-0 w-full bg-background/95 backdrop-blur-md border-b border-border px-6 py-4"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}
