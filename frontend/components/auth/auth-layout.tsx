import type { ReactNode } from "react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { LexAtlasMark } from "@/components/auth/lexatlas-mark";
import { cn } from "@/lib/utils";

const DEFAULT_MARKETING_TITLE = "Retrieve verified Acts with mapped references.";
const DEFAULT_MARKETING_BODY =
  "LexAtlas is an academic information retrieval prototype for certified Sri Lankan Acts. Search the gazette corpus and inspect mapped relationships. It does not provide legal advice.";

export function AuthLayout({
  kicker = "Gazette access",
  title,
  description,
  children,
  footer,
  belowCard,
  marketingTitle = DEFAULT_MARKETING_TITLE,
  marketingBody = DEFAULT_MARKETING_BODY,
}: {
  kicker?: string;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  belowCard?: ReactNode;
  marketingTitle?: string;
  marketingBody?: string;
}) {
  return (
    <div className="flex min-h-svh flex-col bg-background">
      <div className="h-2 bg-destructive" aria-hidden="true" />
      <div className="h-px bg-ring" aria-hidden="true" />
      <div className="grid min-h-0 flex-1 lg:grid-cols-2">
        <section className="relative hidden overflow-hidden bg-primary lg:block">
          <img
            src="/auth/panel.png"
            alt=""
            className="absolute inset-0 size-full object-cover"
          />
          <div className="absolute inset-0 bg-primary/75" />
          <div
            className="absolute inset-0 opacity-30"
            style={{ backgroundImage: "url(/auth/parchment.svg)" }}
            aria-hidden="true"
          />
          <div className="relative flex h-full min-h-svh flex-col justify-between p-12">
            <LexAtlasMark inverted />
            <div className="flex max-w-lg flex-col gap-4 text-primary-foreground">
              <p className="text-xs tracking-[0.28em] uppercase text-ring">Sri Lankan legal gazette</p>
              <h2 className="font-serif text-4xl leading-tight">{marketingTitle}</h2>
              <p className="text-sm leading-relaxed text-primary-foreground/85">{marketingBody}</p>
            </div>
          </div>
        </section>
        <section
          className={cn(
            "flex items-center justify-center bg-background p-6",
            "bg-[url(/auth/parchment.svg)] bg-repeat"
          )}
        >
          <div className="flex w-full max-w-md flex-col gap-6">
            <LexAtlasMark className="lg:hidden" />
            <Card className="rounded-[var(--radius)]">
              <CardHeader className="flex flex-col gap-3 border-b">
                <p className="text-xs tracking-[0.22em] uppercase text-muted-foreground">{kicker}</p>
                <Separator className="bg-ring" />
                <CardTitle className="font-serif text-3xl">{title}</CardTitle>
                {description ? <CardDescription>{description}</CardDescription> : null}
              </CardHeader>
              <CardContent className="pt-(--card-spacing)">{children}</CardContent>
              {footer ? <CardFooter className="flex-col items-start">{footer}</CardFooter> : null}
            </Card>
            {belowCard}
          </div>
        </section>
      </div>
    </div>
  );
}
