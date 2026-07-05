"use client";

export function StatusBadge({ value }: { value: string | null | undefined }) {
  if (!value) return null;
  const status = value.toUpperCase();
  const tone =
    status.includes("VERIFIED") || status.includes("PROCESSED") || status.includes("COMPLETED")
      ? "success"
      : status.includes("FAILED") || status.includes("REJECTED")
        ? "danger"
        : status.includes("PENDING") || status.includes("REVIEW") || status.includes("PROCESSING")
          ? "warning"
          : "neutral";
  return <span className={`badge ${tone}`}>{value.replaceAll("_", " ")}</span>;
}
