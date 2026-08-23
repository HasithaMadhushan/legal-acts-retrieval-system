"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { forgotPassword } from "@/lib/api";
import { AuthLayout } from "@/components/auth/auth-layout";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [detail, setDetail] = useState("");
  const [resetUrl, setResetUrl] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      const response = await forgotPassword(email);
      setDetail(response.detail);
      setResetUrl(response.reset_url ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to request a reset.");
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthLayout
      kicker="Account recovery"
      title="Forgot password"
      description="If the email is registered, a one-time reset link will be issued."
      marketingTitle="Recover access to the gazette."
      marketingBody="Request a reset for a registered account. In this academic deployment the link is shown in development instead of being emailed. This system does not provide legal advice."
    >
      <form className="flex flex-col gap-5" onSubmit={submit}>
        <FieldGroup>
          {error ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          {detail ? (
            <Alert>
              <AlertTitle>Check the issued link</AlertTitle>
              <AlertDescription>
                {detail}
                {resetUrl ? (
                  <>
                    {" "}
                    Development reset URL:{" "}
                    <Link href={resetUrl} className="underline">
                      Open reset page
                    </Link>
                  </>
                ) : null}
              </AlertDescription>
            </Alert>
          ) : null}
          <Field>
            <FieldLabel htmlFor="email" className="text-xs tracking-[0.18em] uppercase text-muted-foreground">
              Email
            </FieldLabel>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="name@example.com"
              autoComplete="email"
              required
              className="h-10"
            />
          </Field>
        </FieldGroup>
        <Button type="submit" size="lg" disabled={pending} className="w-full">
          {pending ? "Sending..." : "Send reset link"}
        </Button>
        <Button variant="link" render={<Link href="/login" />} nativeButton={false}>
          Back to sign in
        </Button>
      </form>
    </AuthLayout>
  );
}
