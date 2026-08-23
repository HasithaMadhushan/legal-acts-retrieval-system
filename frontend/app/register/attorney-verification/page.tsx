"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { submitLawyerVerification } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { AuthLayout } from "@/components/auth/auth-layout";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

export default function AttorneyVerificationPage() {
  const router = useRouter();
  const [enrollmentNumber, setEnrollmentNumber] = useState("");
  const [proofName, setProofName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
    }
  }, [router]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (!file) {
      setError("Upload a PDF, JPEG, or PNG proof of enrollment.");
      return;
    }
    setPending(true);
    try {
      const formData = new FormData();
      formData.set("enrollment_number", enrollmentNumber);
      formData.set("file", file);
      await submitLawyerVerification(formData);
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to submit verification.");
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthLayout
      kicker="Attorney verification"
      title="Confirm enrollment"
      description="Your account stays General User until an administrator approves Attorney-at-Law access."
      marketingTitle="Enrollment review before lawyer tools."
      marketingBody="Submit your Supreme Court enrollment number and proof. Administrators review requests. This system does not provide legal advice."
    >
      {submitted ? (
        <div className="flex flex-col gap-4">
          <Alert>
            <AlertTitle>Request submitted</AlertTitle>
            <AlertDescription>
              Your attorney verification is pending administrator review. You can continue as a General
              User until the request is approved.
            </AlertDescription>
          </Alert>
          <Button render={<Link href="/search" />} nativeButton={false}>
            Continue to search
          </Button>
        </div>
      ) : (
        <form className="flex flex-col gap-5" onSubmit={submit}>
          <FieldGroup>
            {error ? (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
            <Field>
              <FieldLabel
                htmlFor="enrollment"
                className="text-xs tracking-[0.18em] uppercase text-muted-foreground"
              >
                Enrollment number
              </FieldLabel>
              <Input
                id="enrollment"
                value={enrollmentNumber}
                onChange={(event) => setEnrollmentNumber(event.target.value)}
                placeholder="e.g. SL-12345"
                required
                className="h-10"
              />
            </Field>
            <Field>
              <FieldLabel
                htmlFor="proof"
                className="text-xs tracking-[0.18em] uppercase text-muted-foreground"
              >
                Proof of enrollment
              </FieldLabel>
              <Input
                id="proof"
                type="file"
                accept=".pdf,application/pdf,image/jpeg,image/png,.jpg,.jpeg,.png"
                onChange={(event) => {
                  const nextFile = event.target.files?.[0] ?? null;
                  setFile(nextFile);
                  setProofName(nextFile?.name ?? "");
                }}
                required
                className="h-10"
              />
              <FieldDescription>
                {proofName || "PDF, JPEG, or PNG. Administrators use this to approve Attorney-at-Law access."}
              </FieldDescription>
            </Field>
          </FieldGroup>
          <Button type="submit" size="lg" disabled={pending} className="w-full">
            {pending ? "Submitting..." : "Submit for review"}
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
