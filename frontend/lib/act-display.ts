type ActTitleFields = {
  title: string | null | undefined;
  act_number?: string | null;
  year?: number | null;
  source_file_name?: string | null;
};

const PLACEHOLDER_TITLE_PATTERNS = [
  /documents\.gov\.lk/i,
  /can be downloaded/i,
  /^this act\b/i,
  /^untitled$/i,
  /^pdf document$/i
];

export function isPlaceholderActTitle(title: string | null | undefined) {
  const normalized = title?.trim() ?? "";
  if (!normalized) return true;
  if (normalized.length < 4) return true;
  return PLACEHOLDER_TITLE_PATTERNS.some((pattern) => pattern.test(normalized));
}

export function displayActTitle(
  act: ActTitleFields | null | undefined,
  fallback = "Untitled Act"
) {
  if (!act) return fallback;

  const title = act.title?.trim() ?? "";
  if (!isPlaceholderActTitle(title)) return title;

  if (act.act_number && act.year) {
    return `Act No. ${act.act_number} of ${act.year}`;
  }
  if (act.act_number) return `Act No. ${act.act_number}`;
  if (act.year) return `Act of ${act.year}`;

  const fileStem = act.source_file_name
    ?.replace(/\.pdf$/i, "")
    .replace(/[_-]+/g, " ")
    .trim();
  if (fileStem && fileStem.length > 3) return fileStem;

  return fallback;
}

export function displayActTitleWithMeta(act: ActTitleFields | null | undefined) {
  const title = displayActTitle(act);
  const numberPart = act?.act_number ? `No. ${act.act_number}` : null;
  const yearPart = act?.year ? `of ${act.year}` : null;
  const suffix = [numberPart, yearPart].filter(Boolean).join(" ");
  if (!suffix || title.includes(suffix)) return title;
  return `${title} (${suffix})`;
}
