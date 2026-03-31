export default function JobsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex-1 w-full flex flex-col relative overflow-hidden">
      {children}
    </div>
  );
}
