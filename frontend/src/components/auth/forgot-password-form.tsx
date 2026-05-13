'use client';

import { cn } from '@/lib/utils';
import { createClient } from '@/lib/supabase/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { AlertCircle, MailCheck } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';

const spring = { type: 'spring' as const, stiffness: 100, damping: 20 };
const stagger = (i: number) => ({ ...spring, delay: i * 0.08 });

export function ForgotPasswordForm({
  className,
  ...props
}: React.ComponentPropsWithoutRef<'div'>) {
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    const supabase = createClient();
    setIsLoading(true);
    setError(null);

    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/auth/update-password`,
      });
      if (error) throw error;
      setIsSuccess(true);
    } catch (error: unknown) {
      setError(error instanceof Error ? error.message : 'An error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={cn('flex flex-col', className)} {...props}>
      <AnimatePresence mode="wait">
        {isSuccess ? (
          <motion.div
            key="success"
            className="flex flex-col items-center text-center gap-4"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={spring}
          >
            <div className="w-14 h-14 rounded-2xl bg-green-500/10 flex items-center justify-center">
              <MailCheck className="w-7 h-7 text-green-500" />
            </div>
            <h1 className="text-3xl font-bold tracking-tight">
              Check your email
            </h1>
            <p className="text-muted-foreground text-sm max-w-xs">
              We&apos;ve sent a password reset link to your email address.
              Click the link to set a new password.
            </p>
            <Button asChild variant="outline" className="w-full mt-2">
              <Link href="/auth/login">Back to sign in</Link>
            </Button>
          </motion.div>
        ) : (
          <motion.div
            key="form"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, y: -20 }}
            transition={spring}
          >
            <form
              onSubmit={(e) => {
                void handleForgotPassword(e);
              }}
            >
              <div className="flex flex-col gap-5">
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={stagger(0)}
                >
                  <h1 className="text-3xl font-bold tracking-tight">
                    Reset your password
                  </h1>
                  <p className="text-muted-foreground mt-1 text-sm">
                    Enter your email and we&apos;ll send you a reset link
                  </p>
                </motion.div>

                <motion.div
                  className="grid gap-2"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={stagger(1)}
                >
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </motion.div>

                {error && (
                  <div className="flex items-center gap-2 text-sm text-destructive">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    {error}
                  </div>
                )}

                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={stagger(2)}
                >
                  <Button
                    type="submit"
                    className="w-full"
                    disabled={isLoading}
                  >
                    {isLoading ? 'Sending...' : 'Send reset link'}
                  </Button>
                </motion.div>

                <motion.p
                  className="text-center text-sm text-muted-foreground"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={stagger(3)}
                >
                  Remember your password?{' '}
                  <Link
                    href="/auth/login"
                    className="text-foreground font-medium hover:underline underline-offset-4"
                  >
                    Sign in
                  </Link>
                </motion.p>
              </div>
            </form>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
