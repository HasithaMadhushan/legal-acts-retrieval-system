import Link from "next/link";

export default function NotFoundPage() {
  return (
    <div className="mx-auto flex max-w-xl flex-col gap-4 py-16">
      <h1 className="font-serif text-3xl font-semibold">Page not found</h1>
      <p className="text-sm text-muted-foreground">
        That address is not a LexAtlas page. Check the link or continue from search.
      </p>
      <Link href="/search" className="w-fit text-sm underline">
        Go to search
      </Link>
    </div>
  );
}
