"use client";

import { FormEvent, useState } from "react";
import { processAct, uploadAct } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { FileText, Upload } from "lucide-react";

const MAX_UPLOAD_SIZE_MB = 50;
const MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024;

export function UploadDropzone() {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [actNumber, setActNumber] = useState("");
  const [year, setYear] = useState("");
  const [category, setCategory] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [processAfterUpload, setProcessAfterUpload] = useState(true);
  const [uploading, setUploading] = useState(false);
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
      setUploading(true);
      const act = await uploadAct(formData);
      if (processAfterUpload) {
        await processAct(act.id);
        setMessage(`Uploaded ${act.title}. Processing has started; Admin verification is still required.`);
      } else {
        setMessage(`Uploaded ${act.title}. It is awaiting processing and Admin verification.`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed. Check the PDF and try again.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <form className="flex flex-col gap-5" onSubmit={submit}>
      <section className="space-y-2">
        <p className="text-[11px] font-semibold tracking-[0.12em] text-[#92681f] uppercase">1 · Choose file</p>
        <label htmlFor="file" className="flex min-h-52 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-[#b8955a] bg-card px-6 text-center hover:bg-accent/30">
          <span className="mb-3 flex size-12 items-center justify-center rounded-full bg-accent text-[#92681f]"><Upload className="size-5" aria-hidden /></span>
          <span className="font-semibold">Drop the Act PDF here, or <span className="text-[#92681f] underline">browse</span></span>
          <span className="mt-2 text-xs text-muted-foreground">PDF only · max {MAX_UPLOAD_SIZE_MB} MB</span>
        </label>
        <input id="file" className="sr-only" type="file" accept="application/pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        {file ? (
          <Card className="rounded-lg"><CardContent className="flex items-center gap-3 px-4 py-3">
            <span className="flex size-9 items-center justify-center rounded-md bg-accent text-[#92681f]"><FileText className="size-4" /></span>
            <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold">{file.name}</p><p className="text-xs text-muted-foreground">{(file.size / (1024 * 1024)).toFixed(1)} MB</p></div>
            <Button type="button" variant="outline" size="sm" onClick={() => setFile(null)}>Remove</Button>
          </CardContent></Card>
        ) : null}
      </section>

      <section className="space-y-2">
        <p className="text-[11px] font-semibold tracking-[0.12em] text-[#92681f] uppercase">2 · Metadata <span className="normal-case tracking-normal text-muted-foreground">(optional — extraction can fill these later)</span></p>
        <Card className="rounded-lg"><CardContent className="grid gap-4 px-4 py-4 sm:grid-cols-2">
          <div className="space-y-1.5 sm:col-span-2"><Label htmlFor="title">Title override</Label><Input id="title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Personal Data Protection (Amendment) Act" /></div>
          <div className="space-y-1.5"><Label htmlFor="actNumber">Optional Act number</Label><Input id="actNumber" value={actNumber} onChange={(event) => setActNumber(event.target.value)} placeholder="22" /></div>
          <div className="space-y-1.5"><Label htmlFor="year">Optional year</Label><Input id="year" value={year} onChange={(event) => setYear(event.target.value)} inputMode="numeric" placeholder="2025" /></div>
          <div className="space-y-1.5"><Label htmlFor="category">Category</Label><Input id="category" value={category} onChange={(event) => setCategory(event.target.value)} placeholder="Data protection & privacy" /></div>
          <div className="space-y-1.5"><Label htmlFor="sourceUrl">Source URL</Label><Input id="sourceUrl" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://documents.gov.lk/…" /></div>
        </CardContent></Card>
      </section>

      <section className="space-y-2">
        <p className="text-[11px] font-semibold tracking-[0.12em] text-[#92681f] uppercase">3 · Process after upload</p>
        <Card className="rounded-lg"><CardContent className="flex items-center gap-3 px-4 py-4">
          <Checkbox id="processAfterUpload" checked={processAfterUpload} onCheckedChange={(checked) => setProcessAfterUpload(Boolean(checked))} />
          <Label htmlFor="processAfterUpload" className="font-normal">Create processing job immediately after upload</Label>
          <span className="ml-auto hidden text-xs text-muted-foreground sm:block">Parser: Docling → PyMuPDF fallback</span>
        </CardContent></Card>
      </section>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {message ? <p className="text-sm text-[#22684a]">{message}</p> : null}
      <div className="flex justify-end"><Button type="submit" disabled={uploading}>{uploading ? "Uploading…" : processAfterUpload ? "Upload & process" : "Save as uploaded only"}</Button></div>
    </form>
  );
}
