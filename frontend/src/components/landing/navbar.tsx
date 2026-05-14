'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState, type ReactNode } from 'react';

export function Navbar({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isLanding = pathname === '/';
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    if (!isLanding) return;
    const onScroll = () => setScrolled(window.scrollY > 80);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [isLanding]);

  return (
    <nav
      className={
        isLanding
          ? `fixed top-0 left-0 w-full z-50 transition-all duration-300 ${
              scrolled
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
        {children}
      </div>
    </nav>
  );
}
