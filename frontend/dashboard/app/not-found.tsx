import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-muted p-6">
      <div className="max-w-md rounded-lg border border-border bg-background p-8 text-center">
        <p className="font-display text-5xl">404</p>
        <h1 className="mt-4 text-xl font-bold uppercase">Page not found</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          This route is not part of the Bottleneck operations console.
        </p>
        <Button asChild className="mt-6">
          <Link href="/">Return to command center</Link>
        </Button>
      </div>
    </main>
  );
}
