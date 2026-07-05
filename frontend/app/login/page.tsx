"use client";

import { FormEvent, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { login } from "@/lib/api";
import { setSession } from "@/lib/auth";
import { LegalDisclaimer } from "@/components/legal-disclaimer";

export default function LoginPage() {
  return (
    <Suspense fallback={<p>Loading login...</p>}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("AdminPass123!");
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const response = await login(email, password);
      setSession(response.access_token, response.role);
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
    }
  }

  return (
    <div className="grid">
      <LegalDisclaimer />
      <form className="panel grid" onSubmit={submit}>
        <h1>Login</h1>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        </div>
        {error ? <p className="error">{error}</p> : null}
        <button type="submit">Sign in</button>
      </form>
    </div>
  );
}
