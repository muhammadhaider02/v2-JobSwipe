export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex-1 w-full flex flex-col mx-auto max-w-5xl p-5 pt-4">
      {children}
    </div>
  );
}
