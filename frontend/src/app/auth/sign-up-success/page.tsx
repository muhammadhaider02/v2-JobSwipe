import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { MailCheck } from 'lucide-react';

export default function SignUpSuccessPage() {
  return (
    <div className="flex flex-col items-center text-center gap-4">
      <div className="w-14 h-14 rounded-2xl bg-green-500/10 flex items-center justify-center">
        <MailCheck className="w-7 h-7 text-green-500" />
      </div>
      <h1 className="text-3xl font-bold tracking-tight">Check your email</h1>
      <p className="text-muted-foreground text-sm max-w-xs">
        We&apos;ve sent you a confirmation link. Please check your email and
        click the link to activate your account.
      </p>
      <Button asChild variant="outline" className="w-full mt-2">
        <Link href="/auth/login">Back to sign in</Link>
      </Button>
    </div>
  );
}
