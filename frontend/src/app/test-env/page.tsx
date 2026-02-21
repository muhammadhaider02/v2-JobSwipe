export default function TestEnvPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Environment Variables Test</h1>
      <div className="space-y-2">
        <p>
          <strong>SUPABASE_URL:</strong>{' '}
          {process.env.NEXT_PUBLIC_SUPABASE_URL || 'NOT FOUND'}
        </p>
        <p>
          <strong>SUPABASE_KEY:</strong>{' '}
          {process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_OR_ANON_KEY
            ? 'FOUND'
            : 'NOT FOUND'}
        </p>
      </div>
    </div>
  );
}
