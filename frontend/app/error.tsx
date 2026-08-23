"use client";

export default function AppError({
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto flex max-w-xl flex-col gap-4 py-16">
      <h1 className="font-serif text-3xl font-semibold">Something went wrong</h1>
      <p className="text-sm text-muted-foreground">
        The page could not be loaded. Try again, or return to search.
      </p>
      <button type="button" className="w-fit text-sm underline" onClick={() => reset()}>
        Try again
      </button>
    </div>
  );
}
