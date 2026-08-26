import type { RelationshipRow, RelationshipType, VerificationStatus } from "@/lib/types";

export const DOSSIER_FAMILIES = [
  "amends",
  "inserts",
  "refers",
  "incoming",
  "internal",
  "unresolved"
] as const;

export type DossierFamily = (typeof DOSSIER_FAMILIES)[number];

export type DossierCitation = {
  id: string;
  relationshipType: RelationshipType;
  direction: "outgoing" | "incoming";
  sectionId: string | null;
  sectionNumber: string | null;
  sectionHeading: string | null;
  rawText: string;
  snippet: string;
  status: VerificationStatus;
  mapped: boolean;
};

export type DossierActGroup = {
  key: string;
  family: DossierFamily;
  counterpartId: string | null;
  counterpartLabel: string;
  count: number;
  pending: boolean;
  types: string[];
  citations: DossierCitation[];
};

export type DossierSection = {
  family: DossierFamily;
  title: string;
  groups: DossierActGroup[];
};

const FAMILY_TITLE: Record<DossierFamily, string> = {
  amends: "Amends / repeals",
  inserts: "Inserts / adds",
  refers: "Refers to",
  incoming: "Cited by",
  internal: "Within this Act",
  unresolved: "Unresolved"
};

export function buildRelationshipDossier(
  rows: readonly RelationshipRow[],
  focusId: string
): DossierSection[] {
  const buckets = new Map<string, RelationshipRow[]>();
  for (const row of rows) {
    const family = familyForRow(row, focusId);
    const counterpart = counterpartFor(row, family);
    const key = `${family}|${counterpart.id ?? counterpart.label}`;
    const bucket = buckets.get(key);
    if (bucket) bucket.push(row);
    else buckets.set(key, [row]);
  }

  const groupsByFamily = new Map<DossierFamily, DossierActGroup[]>();
  for (const [key, members] of buckets) {
    const first = members[0];
    if (!first) continue;
    const family = key.slice(0, key.indexOf("|")) as DossierFamily;
    const types = [...new Set(members.map((member) => member.relationship_type))].sort((left, right) =>
      left.localeCompare(right)
    );
    const counterpart = counterpartFor(first, family);
    const group: DossierActGroup = {
      key,
      family,
      counterpartId: counterpart.id,
      counterpartLabel: counterpart.label,
      count: members.length,
      pending: members.some((member) => member.verification_status !== "VERIFIED"),
      types,
      citations: members.map(toCitation)
    };
    const list = groupsByFamily.get(family);
    if (list) list.push(group);
    else groupsByFamily.set(family, [group]);
  }

  return DOSSIER_FAMILIES.flatMap((family) => {
    const groups = groupsByFamily.get(family);
    if (!groups?.length) return [];
    groups.sort((left, right) => right.count - left.count || left.counterpartLabel.localeCompare(right.counterpartLabel));
    return [{ family, title: FAMILY_TITLE[family], groups }];
  });
}

export function dossierNeighborCount(sections: readonly DossierSection[]): number {
  const ids = new Set<string>();
  for (const section of sections) {
    if (section.family === "internal" || section.family === "unresolved") continue;
    for (const group of section.groups) {
      if (group.counterpartId) ids.add(group.counterpartId);
    }
  }
  return ids.size;
}

export function dossierGroupKeyFromEdge(
  focusId: string,
  edge: { source: string; target: string; label: string }
): string {
  const incoming = edge.target === focusId && edge.source !== focusId;
  const family = incoming ? "incoming" : familyFromType(edge.label);
  const counterpartId = incoming ? edge.source : edge.target;
  return `${family}|${counterpartId}`;
}

export function dossierKeyForAct(
  sections: readonly DossierSection[],
  actId: string
): string | null {
  let best: DossierActGroup | null = null;
  for (const section of sections) {
    for (const group of section.groups) {
      if (group.counterpartId !== actId) continue;
      if (!best || group.count > best.count) best = group;
    }
  }
  return best?.key ?? null;
}

function familyForRow(row: RelationshipRow, focusId: string): DossierFamily {
  if (row.direction === "incoming") return "incoming";
  if (row.target_act_id === focusId || row.target_act_id === row.source_act_id) return "internal";
  if (isBareInternalCitation(row)) return "internal";
  if (!row.mapped || !row.target_act_id) return "unresolved";
  return familyFromType(row.relationship_type);
}

function counterpartFor(row: RelationshipRow, family: DossierFamily): { id: string | null; label: string } {
  if (family === "incoming") {
    return { id: row.source_act_id, label: row.source_act_title ?? row.source_act_id };
  }
  if (family === "internal") {
    return {
      id: row.target_act_id ?? row.source_act_id,
      label: row.target_act_title ?? row.source_act_title ?? "This Act"
    };
  }
  if (family === "unresolved") {
    return { id: null, label: unresolvedTargetLabel(row) };
  }
  return {
    id: row.target_act_id,
    label: row.target_act_title ?? row.target_act_title_raw ?? row.target_act_id ?? "Mapped Act"
  };
}

function familyFromType(type: string): DossierFamily {
  if (type === "AMENDS" || type === "REPEALS" || type === "SUBSTITUTES") return "amends";
  if (type === "INSERTS" || type === "ADDS") return "inserts";
  return "refers";
}

const INTERNAL_CITE =
  /\b((first|second|third|fourth|fifth)\s+)?(section|subsection|paragraph|schedule|item|proviso|part)\b/i;

function isBareInternalCitation(
  row: Pick<
    RelationshipRow,
    | "target_act_id"
    | "target_act_number"
    | "target_act_year"
    | "target_act_title_raw"
    | "raw_reference_text"
  >
) {
  if (row.target_act_id || row.target_act_number || row.target_act_year) return false;
  const title = row.target_act_title_raw ?? "";
  const raw = row.raw_reference_text ?? "";
  if (extractCitedActName(title) || extractCitedActName(raw)) return false;
  if (/Chapter\s+\d+/i.test(title) || /Chapter\s+\d+/i.test(raw)) return false;
  return INTERNAL_CITE.test(raw) || /principal enactment|\bthereof\b|\bthis Act\b/i.test(raw);
}

export function unresolvedTargetLabel(
  row: Pick<
    RelationshipRow,
    "target_act_title_raw" | "raw_reference_text" | "target_act_number" | "target_act_year"
  >
): string {
  const fromTitle = extractCitedActName(row.target_act_title_raw ?? "");
  if (fromTitle) return fromTitle;
  const fromText = extractCitedActName(row.raw_reference_text ?? "");
  if (fromText) return fromText;
  const source = [row.target_act_title_raw, row.raw_reference_text].filter(Boolean).join(" ");
  const chapter = /Chapter\s+(\d+[A-Z]?)/i.exec(source);
  if (chapter?.[1]) return `Chapter ${chapter[1]}`;
  if (row.target_act_number && row.target_act_year) {
    return `Act No. ${row.target_act_number} of ${row.target_act_year}`;
  }
  return "Unmatched target";
}

const CITED_ACT_NAME =
  /\b([A-Z][A-Za-z0-9'’]*(?:\s+(?:and|of|the|for|&|[A-Z][A-Za-z0-9'’-]*)){0,5})\s+(Act|Ordinance)\b/g;

const WEAK_ACT_TITLES = new Set(["fund act", "trust act", "the code", "code"]);

function extractCitedActName(text: string): string | null {
  const padded = text.replace(/([a-z])(Act|Ordinance)\b/g, "$1 $2");
  let best: string | null = null;
  for (const match of padded.matchAll(CITED_ACT_NAME)) {
    const name = tidyActName(`${match[1] ?? ""} ${match[2] ?? ""}`);
    if (name.length < 5 || WEAK_ACT_TITLES.has(name.toLowerCase())) continue;
    if (!best || name.length > best.length) best = name;
  }
  return best;
}

function tidyActName(name: string): string {
  return name.replace(/^(?:The|And|Of)\s+/i, "").replace(/\s+/g, " ").trim();
}

function toCitation(row: RelationshipRow): DossierCitation {
  const incoming = row.direction === "incoming";
  return {
    id: row.id,
    relationshipType: row.relationship_type,
    direction: row.direction,
    sectionId: incoming ? row.source_section_id : row.target_section_id ?? row.source_section_id,
    sectionNumber: incoming ? row.source_section_number : row.target_section_number ?? row.source_section_number,
    sectionHeading: incoming ? row.source_section_heading : row.target_section_heading ?? row.source_section_heading,
    rawText: row.raw_reference_text,
    snippet: row.context_snippet,
    status: row.verification_status,
    mapped: row.mapped
  };
}
