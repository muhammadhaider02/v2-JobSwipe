import Link from 'next/link';

export function LandingFooter() {
  return (
    <footer className="w-full border-t border-border bg-background">
      <div className="max-w-6xl mx-auto px-6 py-10">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-lg">JobSwipe</span>
            <span className="text-muted-foreground text-sm">
              &middot; Apply Less, Land More
            </span>
          </div>
          <div className="flex items-center gap-6 text-sm text-muted-foreground">
            <Link
              href="/auth/sign-up"
              className="hover:text-foreground transition-colors"
            >
              Get Started
            </Link>
            <Link
              href="/auth/login"
              className="hover:text-foreground transition-colors"
            >
              Sign In
            </Link>
          </div>
        </div>
        <div className="mt-6 pt-6 border-t border-border text-center text-xs text-muted-foreground">
          &copy; {new Date().getFullYear()} JobSwipe. All rights reserved.
        </div>
      </div>
    </footer>
  );
}
