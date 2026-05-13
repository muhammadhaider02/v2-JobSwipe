import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';
import { QueryProvider } from '@/providers/query-provider';
import { ThemeProvider } from 'next-themes';
import { AuthButton } from '@/components/auth/auth-button';
import { Navbar } from '@/components/landing/navbar';

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
    'Apply less, land more. AI-powered job matching, resume optimization, and one-swipe applications.',
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
                <Navbar>
                  <AuthButton />
                </Navbar>

                <div className="flex-1 w-full flex flex-col">
                  {children}
                </div>
              </div>
            </main>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
