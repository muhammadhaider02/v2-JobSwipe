'use client';

import { cn } from '@/lib/utils';
import { createClient } from '@/lib/supabase/client';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState, useEffect } from 'react';

export function LoginForm({
  className,
  ...props
}: React.ComponentPropsWithoutRef<'div'>) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isMagicLoading, setIsMagicLoading] = useState(false);
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const [magicSent, setMagicSent] = useState(false);
  const router = useRouter();

  // Clear any expired sessions on mount
  useEffect(() => {
    const clearExpiredSession = async () => {
      const supabase = createClient();
      try {
        // Try to get the user, which will attempt to refresh the token
        const { data: { user }, error } = await supabase.auth.getUser();
        
        // If there's an error (like expired token), sign out
        if (error || !user) {
          await supabase.auth.signOut();
        }
      } catch (err) {
        // Silently handle any errors during session cleanup
        console.error('Session cleanup error:', err);
        try {
          const supabase = createClient();
          await supabase.auth.signOut();
        } catch {
          // Ignore signout errors
        }
      }
    };

    clearExpiredSession();
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    const supabase = createClient();
    setIsLoading(true);
    setError(null);

    try {
      // First, ensure we're signed out of any expired session
      await supabase.auth.signOut();
      
      // Now sign in with fresh credentials
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (error) throw error;
      
      // Force a hard navigation to ensure middleware runs
      window.location.href = '/onboarding';
    } catch (error: unknown) {
      setError(error instanceof Error ? error.message : 'An error occurred');
      setIsLoading(false);
    }
  };

  const handleMagicLink = async () => {
    const supabase = createClient();
    setIsMagicLoading(true);
    setError(null);
    try {
      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: `${window.location.origin}/auth/confirm?next=/onboarding`,
        },
      });
      if (error) throw error;
      setMagicSent(true);
    } catch (error: unknown) {
      setError(error instanceof Error ? error.message : 'An error occurred');
    } finally {
      setIsMagicLoading(false);
    }
  };

  const handleLoginWithGoogle = async () => {
    const supabase = createClient();
    setError(null);
    setIsGoogleLoading(true);
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/auth/confirm?next=/onboarding`,
        },
      });
      if (error) throw error;
      // Browser will be redirected automatically, no need to handle data.url
    } catch (error: unknown) {
      setError(error instanceof Error ? error.message : 'An error occurred');
      setIsGoogleLoading(false);
    }
    // Don't set loading to false here - browser will redirect
  };

  return (
    <div className={cn('flex flex-col gap-6', className)} {...props}>
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">Login</CardTitle>
          <CardDescription>
            Enter your email below to login to your account
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={(e) => {
              void handleLogin(e);
            }}
          >
            <div className="flex flex-col gap-4">
              <div className="grid gap-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="hi@example.com"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <div className="flex items-center">
                  <Label htmlFor="password">Password</Label>
                  <Link
                    href="/auth/forgot-password"
                    className="ml-auto inline-block text-sm underline-offset-4 hover:underline"
                  >
                    Forgot your password?
                  </Link>
                </div>
                <Input
                  id="password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              {error && <p className="text-sm text-red-500">{error}</p>}
              {magicSent && (
                <p className="text-sm text-green-600">
                  Magic link sent. Check your email to log in.
                </p>
              )}
              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? 'Logging in...' : 'Login'}
              </Button>
              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={() => {
                  void handleLoginWithGoogle();
                }}
                disabled={isGoogleLoading}
              >
                {isGoogleLoading
                  ? 'Redirecting to Google…'
                  : 'Login with Google'}
              </Button>
              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={() => {
                  void handleMagicLink();
                }}
                disabled={isMagicLoading || !email}
              >
                {isMagicLoading
                  ? 'Sending magic link...'
                  : 'Login with Magic Link'}
              </Button>
            </div>
            <div className="mt-4 text-center text-sm">
              Don&apos;t have an account?{' '}
              <Link
                href="/auth/sign-up"
                className="underline underline-offset-4"
              >
                Sign up
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
