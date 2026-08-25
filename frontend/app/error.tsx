"use client";

type AppErrorProps = Readonly<{
  error: Error & { digest?: string };
  reset: () => void;
}>;

export default function AppError({ error, reset }: AppErrorProps) {
  return (
    <div className="mx-auto flex max-w-xl flex-col gap-4 py-16">
      <h1 className="font-serif text-3xl font-semibold">Something went wrong</h1>
      <p className="text-sm text-muted-foreground">
        The page could not be loaded. Try again, or return to search.
      </p>
      {error.digest ? (
        <p className="text-xs text-muted-foreground">Reference: {error.digest}</p>
      ) : null}
      <button type="button" className="w-fit text-sm underline" onClick={() => reset()}>
        Try again
      </button>
    </div>
  );
}
