import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';
import { QueryProvider } from '@/providers/query-provider';
import { ThemeProvider } from 'next-themes';
import { AuthButton } from '@/components/auth/auth-button';
import Link from 'next/link';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'JobSwipe',
  description:
    'Your platform to discover opportunities, grow your career and land the right job.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <QueryProvider>
            <main className="min-h-screen flex flex-col items-center bg-background text-foreground">
              <div className="flex-1 w-full flex flex-col items-center">
                <nav className="w-full flex border-b border-b-foreground/10 h-16 bg-background">
                  <div className="w-full flex justify-between items-center p-3 px-6 text-sm">
                    <div className="flex gap-5 items-center font-semibold text-lg hover:text-primary transition-colors">
                      <Link href="/">JobSwipe</Link>
                    </div>
                    <AuthButton />
                  </div>
                </nav>

                <div className="flex-1 w-full flex flex-col">
                  {children}
                </div>

                <footer className="w-full flex items-center justify-center border-t border-t-foreground/10 mx-auto text-center text-xs py-6 bg-background">
                  <p>Built with ❤️ by JobSwipe</p>
                </footer>
              </div>
            </main>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
