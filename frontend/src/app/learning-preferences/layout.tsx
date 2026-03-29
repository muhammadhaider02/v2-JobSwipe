import { AuthButton } from '@/components/auth/auth-button';
import Link from 'next/link';

export default function LearningPreferencesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <main className="min-h-screen flex flex-col items-center bg-background text-foreground">
      <div className="flex-1 w-full flex flex-col items-center">
        <nav className="w-full flex border-b border-b-foreground/10 h-16 bg-background">
          <div className="w-full flex justify-between items-center p-3 px-6 text-sm">
            <div className="flex gap-5 items-center font-semibold text-lg hover:text-primary transition-colors">
              <Link href={'/'}>JobSwipe</Link>
            </div>
            <AuthButton />
          </div>
        </nav>
        <div className="flex-1 w-full flex flex-col">
          {children}
        </div>

        <footer className="w-full flex items-center justify-center border-t border-t-foreground/10 mx-auto text-center text-xs h-18 bg-background">
          <p>Built with ❤️ by JobSwipe</p>
        </footer>
      </div>
    </main>
  );
}
