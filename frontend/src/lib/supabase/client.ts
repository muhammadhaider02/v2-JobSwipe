import { createBrowserClient } from '@supabase/ssr';

export function createClient() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_OR_ANON_KEY;

  if (!supabaseUrl || !supabaseKey) {
    throw new Error(
      `Missing Supabase environment variables. 
      URL: ${supabaseUrl ? 'Found' : 'Missing'}
      Key: ${supabaseKey ? 'Found' : 'Missing'}
      Please check your .env.local file.`,
    );
  }

  return createBrowserClient(supabaseUrl, supabaseKey, {
    auth: {
      // Auto-refresh tokens
      autoRefreshToken: true,
      // Persist session to localStorage
      persistSession: true,
      // Detect session changes in other tabs
      detectSessionInUrl: true,
    },
  });
}
