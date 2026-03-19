import { redirect } from 'next/navigation';
import { createClient } from '@/lib/supabase/server';
import MultiStepResumeForm from '@/components/MultiStepResumeForm';

export default async function OnboardingPage() {
  const supabase = await createClient();

  const { data, error } = await supabase.auth.getUser();
  if (error || !data?.user) {
    redirect('/auth/login');
  }

  const userId = data.user.id;

  return (
    <div className="flex-1 w-full flex flex-col">
      <MultiStepResumeForm userId={userId} />
    </div>
  );
}
