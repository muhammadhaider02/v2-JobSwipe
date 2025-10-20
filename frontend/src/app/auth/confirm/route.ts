import { createClient } from '@/lib/supabase/server';
import { type EmailOtpType } from '@supabase/supabase-js';
import { redirect } from 'next/navigation';
import { type NextRequest } from 'next/server';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const code = searchParams.get('code');
  const token_hash = searchParams.get('token_hash');
  const type = searchParams.get('type') as EmailOtpType | null;
  const next = searchParams.get('next') ?? '/onboarding';

  const supabase = await createClient();

  // Newer Supabase links redirect with a `code` which must be exchanged
  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      redirect(next);
    }
    const err = encodeURIComponent(error?.message ?? 'Code exchange failed');
    redirect(`/auth/error?error=${err}`);
  }

  // Older style links include `token_hash` and `type`
  if (token_hash && type) {
    const { error } = await supabase.auth.verifyOtp({
      type,
      token_hash,
    });
    if (!error) {
      redirect(next);
    }
    const err = encodeURIComponent(error?.message ?? 'OTP verification failed');
    redirect(`/auth/error?error=${err}`);
  }

  redirect(`/auth/error?error=No token hash, type, or code`);
}
