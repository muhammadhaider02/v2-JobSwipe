export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex-1 w-full flex flex-col items-center justify-center px-4 py-6">
      {children}
    </div>
  );
}
