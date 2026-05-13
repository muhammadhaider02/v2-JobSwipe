import { AuthBrandingPanel } from '@/components/auth/auth-branding-panel';

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-[100dvh] w-full grid grid-cols-1 lg:grid-cols-2">
      <div className="hidden lg:block">
        <AuthBrandingPanel />
      </div>
      <div className="flex items-center justify-center px-6 py-12 overflow-y-auto">
        <div className="w-full max-w-sm">{children}</div>
      </div>
    </div>
  );
}
