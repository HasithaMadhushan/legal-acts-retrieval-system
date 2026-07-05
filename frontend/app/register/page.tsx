"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { register } from "@/lib/api";
import { LegalDisclaimer } from "@/components/legal-disclaimer";

export default function RegisterPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    setError("");
    try {
      await register(fullName, email, password);
      setMessage("Account registered as General User. Admins can change roles after verification.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed.");
    }
  }

  return (
    <div className="grid">
      <LegalDisclaimer />
      <form className="panel grid" onSubmit={submit}>
        <h1>Register</h1>
        <div className="field">
          <label htmlFor="fullName">Full name</label>
          <input id="fullName" value={fullName} onChange={(event) => setFullName(event.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        </div>
        {error ? <p className="error">{error}</p> : null}
        {message ? <p>{message} <Link href="/login">Login</Link></p> : null}
        <button type="submit">Create General User account</button>
      </form>
    </div>
  );
}
