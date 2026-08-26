import type { RelationshipListResponse, RelationshipRow } from "@/lib/types";

export const RELATIONSHIP_FETCH_PAGE = 100;

export async function fetchAllRelationshipRows(
  fetchPage: (offset: number, limit: number) => Promise<RelationshipListResponse>
): Promise<{ rows: RelationshipRow[]; list: RelationshipListResponse }> {
  const first = await fetchPage(0, RELATIONSHIP_FETCH_PAGE);
  const rows = [...first.relationships];
  let offset = rows.length;
  while (offset < first.total_results) {
    const page = await fetchPage(offset, RELATIONSHIP_FETCH_PAGE);
    if (!page.relationships.length) break;
    rows.push(...page.relationships);
    offset += page.relationships.length;
  }
  return {
    rows,
    list: { ...first, relationships: rows, total_results: rows.length }
  };
}
