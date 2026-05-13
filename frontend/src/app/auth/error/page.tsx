import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { AlertTriangle } from 'lucide-react';

interface ErrorPageProps {
  searchParams: Promise<{
    error?: string;
  }>;
}

export default async function ErrorPage({ searchParams }: ErrorPageProps) {
  const { error } = await searchParams;
  const errorMessage = error || 'An unexpected error occurred';

  return (
    <div className="flex flex-col items-center text-center gap-4">
      <div className="w-14 h-14 rounded-2xl bg-destructive/10 flex items-center justify-center">
        <AlertTriangle className="w-7 h-7 text-destructive" />
      </div>
      <h1 className="text-3xl font-bold tracking-tight">
        Something went wrong
      </h1>
      <p className="text-muted-foreground text-sm max-w-xs">{errorMessage}</p>
      <div className="flex gap-3 w-full mt-2">
        <Button asChild variant="outline" className="flex-1">
          <Link href="/auth/login">Try again</Link>
        </Button>
        <Button asChild className="flex-1">
          <Link href="/">Go home</Link>
        </Button>
      </div>
    </div>
  );
}
