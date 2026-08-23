"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { login } from "@/lib/api";
import { setSession } from "@/lib/auth";
import { AuthLayout } from "@/components/auth/auth-layout";
import { PasswordField } from "@/components/auth/password-field";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

export default function LoginPage() {
  return (
    <Suspense fallback={<p className="p-6">Loading login...</p>}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const registered = searchParams.get("registered") === "1";
  const reset = searchParams.get("reset") === "1";

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      const response = await login(email, password, rememberMe);
      setSession(response.access_token, response.role, rememberMe);
      const nextPath = searchParams.get("next");
      router.push(
        nextPath ??
          (response.role === "ADMIN"
            ? "/admin/acts"
            : response.role === "LAWYER"
              ? "/lawyer/search"
              : "/search")
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthLayout
      kicker="Gazette access"
      title="Sign in"
      description="Enter your email and password to continue."
      belowCard={
        <p className="text-xs text-muted-foreground">
          Thesis demo accounts: admin@example.com / AdminPass123!, lawyer@example.com /
          LawyerPass123!, user@example.com / UserPass123!
        </p>
      }
    >
      <form className="flex flex-col gap-5" onSubmit={submit}>
        <FieldGroup>
          {registered ? (
            <Alert>
              <AlertDescription>Account created. Sign in to continue.</AlertDescription>
            </Alert>
          ) : null}
          {reset ? (
            <Alert>
              <AlertDescription>Password updated. Sign in with your new password.</AlertDescription>
            </Alert>
          ) : null}
          {error ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
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
          <PasswordField
            id="password"
            label="Password"
            value={password}
            onChange={setPassword}
            visible={showPassword}
            onToggle={() => setShowPassword((value) => !value)}
            autoComplete="current-password"
          />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Field orientation="horizontal">
              <Checkbox
                id="remember"
                checked={rememberMe}
                onCheckedChange={(checked) => setRememberMe(Boolean(checked))}
              />
              <FieldLabel htmlFor="remember" className="font-normal">
                Keep me signed in
              </FieldLabel>
            </Field>
            <Button variant="link" size="sm" render={<Link href="/forgot-password" />} nativeButton={false}>
              Forgot password?
            </Button>
          </div>
        </FieldGroup>
        <Button type="submit" size="lg" disabled={pending} className="w-full">
          {pending ? "Signing in..." : "Sign in"}
        </Button>
        <p className="text-sm text-muted-foreground">
          New to LexAtlas?{" "}
          <Button variant="link" render={<Link href="/register" />} nativeButton={false}>
            Create an account
          </Button>
        </p>
      </form>
    </AuthLayout>
  );
}
