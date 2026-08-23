"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { login, register } from "@/lib/api";
import { setSession } from "@/lib/auth";
import { AuthLayout } from "@/components/auth/auth-layout";
import { PasswordField } from "@/components/auth/password-field";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
  FieldTitle,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { PASSWORD_HINT, passwordMeetsPolicy } from "@/lib/password-policy";

export default function RegisterPage() {
  const router = useRouter();
  const [accountType, setAccountType] = useState("general");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const isAttorney = accountType === "attorney";

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
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
      await register({
        email,
        password,
      });
      if (isAttorney) {
        const session = await login(email, password, false);
        setSession(session.access_token, session.role, false);
        router.push("/register/attorney-verification");
        return;
      }
      router.push("/login?registered=1");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthLayout
      kicker="Create access"
      title="Create an account"
      description="General Users can search verified Acts. Attorney-at-Law access requires enrollment review."
      marketingTitle="Join the gazette reading room."
      marketingBody="Create a General User account to search verified Acts, or request Attorney-at-Law access after enrollment verification. This system does not provide legal advice."
    >
      <form className="flex flex-col gap-5" onSubmit={submit}>
        <FieldGroup>
          {error ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          <FieldSet>
            <FieldLegend className="text-xs tracking-[0.18em] uppercase text-muted-foreground">
              Account type
            </FieldLegend>
            <RadioGroup value={accountType} onValueChange={setAccountType} className="gap-3">
              <FieldLabel htmlFor="account-general">
                <Field orientation="horizontal">
                  <RadioGroupItem value="general" id="account-general" />
                  <FieldContent>
                    <FieldTitle>General User</FieldTitle>
                    <FieldDescription>Search and browse verified legal Acts.</FieldDescription>
                  </FieldContent>
                </Field>
              </FieldLabel>
              <FieldLabel htmlFor="account-attorney">
                <Field orientation="horizontal">
                  <RadioGroupItem value="attorney" id="account-attorney" />
                  <FieldContent>
                    <FieldTitle>Attorney-at-Law</FieldTitle>
                    <FieldDescription>
                      Submit enrollment proof. Access stays General User until an administrator approves.
                    </FieldDescription>
                  </FieldContent>
                </Field>
              </FieldLabel>
            </RadioGroup>
          </FieldSet>
          {isAttorney ? (
            <Alert>
              <AlertTitle>Attorney verification required</AlertTitle>
              <AlertDescription>
                Attorney-at-Law accounts require an enrollment number and proof of enrollment. Your role
                remains General User until an administrator approves the request.
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
          <PasswordField
            id="password"
            label="Password"
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
          {pending
            ? "Continuing..."
            : isAttorney
              ? "Continue to attorney verification"
              : "Create account"}
        </Button>
        <p className="text-sm text-muted-foreground">
          Already have an account?{" "}
          <Button variant="link" render={<Link href="/login" />} nativeButton={false}>
            Sign in
          </Button>
        </p>
      </form>
    </AuthLayout>
  );
}
