import Link from 'next/link';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

interface ErrorPageProps {
  searchParams: Promise<{
    error?: string;
  }>;
}

export default async function ErrorPage({ searchParams }: ErrorPageProps) {
  const { error } = await searchParams;
  const errorMessage = error || 'An unexpected error occurred';
  
  // Provide helpful messages for common errors
  const getHelpfulMessage = (error: string) => {
    if (error.includes('flow_state_not_found')) {
      return 'OAuth flow state not found. This usually happens when cookies are blocked or the redirect URL is misconfigured in Supabase.';
    }
    if (error.includes('No token hash')) {
      return 'Authentication parameters are missing. Please try logging in again.';
    }
    return error;
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl text-red-600">
              Authentication Error
            </CardTitle>
            <CardDescription>
              Something went wrong with your authentication
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-4">
              {getHelpfulMessage(errorMessage)}
            </p>
            
            {errorMessage.includes('flow_state_not_found') && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4">
                <p className="text-xs text-blue-800">
                  <strong>Tip:</strong> Make sure cookies are enabled and the redirect URL 
                  <code className="bg-blue-100 px-1 mx-1 rounded">
                    {typeof window !== 'undefined' ? window.location.origin : ''}/auth/confirm
                  </code>
                  is added to your Supabase project's allowed redirect URLs.
                </p>
              </div>
            )}
            
            <div className="flex gap-2">
              <Button asChild variant="outline" className="flex-1">
                <Link href="/auth/login">Try again</Link>
              </Button>
              <Button asChild className="flex-1">
                <Link href="/">Go home</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
