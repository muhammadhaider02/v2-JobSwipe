import { createClient } from '@/lib/supabase/server';
import { type EmailOtpType } from '@supabase/supabase-js';
import { redirect } from 'next/navigation';
import { type NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const code = searchParams.get('code');
  const token_hash = searchParams.get('token_hash');
  const type = searchParams.get('type') as EmailOtpType | null;
  const next = searchParams.get('next') ?? '/onboarding';
  
  // Check for Supabase error parameters
  const error = searchParams.get('error');
  const error_code = searchParams.get('error_code');
  const error_description = searchParams.get('error_description');

  // If there's an error from Supabase, redirect to error page
  if (error) {
    const errorMsg = error_description || error_code || error;
    redirect(`/auth/error?error=${encodeURIComponent(errorMsg)}`);
  }

  const supabase = await createClient();

  // Newer Supabase links redirect with a `code` which must be exchanged
  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      // Force a hard redirect to ensure session cookies are set
      return NextResponse.redirect(new URL(next, request.url));
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
      // Force a hard redirect to ensure session cookies are set
      return NextResponse.redirect(new URL(next, request.url));
    }
    const err = encodeURIComponent(error?.message ?? 'OTP verification failed');
    redirect(`/auth/error?error=${err}`);
  }

  // No valid authentication parameters found
  redirect(`/auth/login`);
}
