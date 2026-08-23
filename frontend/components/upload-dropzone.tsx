"use client";

import { FormEvent, useState } from "react";
import { uploadAct } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const MAX_UPLOAD_SIZE_MB = 50;
const MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024;

export function UploadDropzone() {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [actNumber, setActNumber] = useState("");
  const [year, setYear] = useState("");
  const [category, setCategory] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    setError("");
    if (!file) {
      setError("Choose a PDF file first.");
      return;
    }
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Only PDF files are accepted.");
      return;
    }
    if (file.type && file.type !== "application/pdf") {
      setError("The selected file is not reported as a PDF by your browser.");
      return;
    }
    if (file.size > MAX_UPLOAD_SIZE_BYTES) {
      setError(`PDF files must be ${MAX_UPLOAD_SIZE_MB} MB or smaller.`);
      return;
    }
    const formData = new FormData();
    formData.set("file", file);
    if (title.trim()) formData.set("title", title.trim());
    if (actNumber.trim()) formData.set("act_number", actNumber.trim());
    if (year.trim()) formData.set("year", year.trim());
    if (category) formData.set("category", category);
    if (sourceUrl) formData.set("source_url", sourceUrl);
    try {
      const act = await uploadAct(formData);
      setMessage(`Uploaded ${act.title}. It is pending processing and Admin verification.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed. Check the PDF and try again.");
    }
  }

  return (
    <form className="panel grid" onSubmit={submit}>
      <div className="field">
        <label htmlFor="file">Legal Act PDF</label>
        <input id="file" type="file" accept="application/pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        <span className="muted">PDF only, maximum {MAX_UPLOAD_SIZE_MB} MB.</span>
      </div>
      <div className="field">
        <Label htmlFor="title">Optional title</Label>
        <Input id="title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Personal Data Protection (Amendment) Act" />
      </div>
      <div className="grid two">
        <div className="field">
          <Label htmlFor="actNumber">Optional Act number</Label>
          <Input id="actNumber" value={actNumber} onChange={(event) => setActNumber(event.target.value)} placeholder="22" />
        </div>
        <div className="field">
          <Label htmlFor="year">Optional year</Label>
          <Input id="year" value={year} onChange={(event) => setYear(event.target.value)} inputMode="numeric" placeholder="2025" />
        </div>
      </div>
      <div className="field">
        <label htmlFor="category">Category</label>
        <input id="category" value={category} onChange={(event) => setCategory(event.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="sourceUrl">Source URL</label>
        <input id="sourceUrl" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} />
      </div>
      {error ? <p className="error">{error}</p> : null}
      {message ? <p>{message}</p> : null}
      <button type="submit">Upload PDF</button>
    </form>
  );
}
