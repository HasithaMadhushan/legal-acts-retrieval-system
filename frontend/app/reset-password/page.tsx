"use client";

import { FormEvent, Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { resetPassword } from "@/lib/api";
import { AuthLayout } from "@/components/auth/auth-layout";
import { PasswordField } from "@/components/auth/password-field";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FieldGroup } from "@/components/ui/field";
import { PASSWORD_HINT, passwordMeetsPolicy } from "@/lib/password-policy";

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<p className="p-6">Loading reset...</p>}>
      <ResetPasswordForm />
    </Suspense>
  );
}

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (!token) {
      setError("This reset link is missing a token.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Password and confirmation do not match.");
      return;
    }
    if (!passwordMeetsPolicy(password)) {
      setError(PASSWORD_HINT);
      return;
    }
    setPending(true);
    try {
      await resetPassword(token, password);
      router.push("/login?reset=1");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reset password.");
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthLayout
      kicker="Account recovery"
      title="Reset password"
      description="Choose a new password for your LexAtlas account."
    >
      <form className="flex flex-col gap-5" onSubmit={submit}>
        <FieldGroup>
          {error ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          <PasswordField
            id="password"
            label="New password"
            value={password}
            onChange={setPassword}
            visible={showPassword}
            onToggle={() => setShowPassword((value) => !value)}
            autoComplete="new-password"
            hint={PASSWORD_HINT}
          />
          <PasswordField
            id="confirm-password"
            label="Confirm password"
            value={confirmPassword}
            onChange={setConfirmPassword}
            visible={showConfirm}
            onToggle={() => setShowConfirm((value) => !value)}
            placeholder="Re-enter password"
            autoComplete="new-password"
          />
        </FieldGroup>
        <Button type="submit" size="lg" disabled={pending} className="w-full">
          {pending ? "Updating..." : "Update password"}
        </Button>
        <Button variant="link" render={<Link href="/login" />} nativeButton={false}>
          Back to sign in
        </Button>
      </form>
    </AuthLayout>
  );
}
