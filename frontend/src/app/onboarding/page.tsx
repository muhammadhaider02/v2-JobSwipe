import { redirect } from 'next/navigation';
import { createClient } from '@/lib/supabase/server';
import MultiStepResumeForm from '@/components/MultiStepResumeForm';

export default async function OnboardingPage() {
  const supabase = await createClient();

  const { data, error } = await supabase.auth.getClaims();
  if (error || !data?.claims) {
    redirect('/auth/login');
  }

  return (
    <div className="flex-1 w-full flex flex-col gap-12">
      <h2 className="font-bold text-2xl">Onboarding</h2>
      <MultiStepResumeForm />
    </div>
  );
}
