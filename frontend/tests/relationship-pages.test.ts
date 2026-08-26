import { describe, expect, it, vi } from "vitest";
import { fetchAllRelationshipRows, RELATIONSHIP_FETCH_PAGE } from "../lib/relationship-pages";
import type { RelationshipListResponse, RelationshipRow } from "../lib/types";

function stubRow(id: string): RelationshipRow {
  return {
    id,
    source_act_id: "vat",
    source_act_title: "Value Added Tax Act",
    source_section_id: "s1",
    source_section_number: "1",
    source_section_heading: "Charge of tax",
    relationship_type: "REFERS_TO",
    target_act_id: "gst",
    target_act_title: "Goods and Services Tax Act",
    target_section_id: "t1",
    target_section_number: "2",
    target_section_heading: "Interpretation",
    target_act_title_raw: null,
    target_act_number: "34",
    target_act_year: 1996,
    target_section_path: null,
    direction: "outgoing",
    mapped: true,
    verification_status: "VERIFIED",
    confidence_score: 0.9,
    raw_reference_text: "Goods and Services Tax Act",
    context_snippet: "as defined in the Goods and Services Tax Act"
  };
}

function page(
  relationships: RelationshipRow[],
  total: number,
  offset = 0
): RelationshipListResponse {
  return {
    scope_type: "act",
    scope_id: "vat",
    relationships,
    summary: {
      total_results: total,
      outgoing_count: total,
      incoming_count: 0,
      mapped_count: total,
      unresolved_count: 0,
      by_relationship_type: {},
      by_verification_status: {}
    },
    limit: RELATIONSHIP_FETCH_PAGE,
    offset,
    total_results: total,
    disclaimer: ""
  };
}

describe("fetchAllRelationshipRows", () => {
  it("walks every page until the table total is loaded", async () => {
    const first = Array.from({ length: RELATIONSHIP_FETCH_PAGE }, (_, index) => stubRow(`a${index}`));
    const second = Array.from({ length: 20 }, (_, index) => stubRow(`b${index}`));
    const fetchPage = vi.fn(async (offset: number) => {
      if (offset === 0) return page(first, 120, 0);
      return page(second, 120, offset);
    });

    const { rows, list } = await fetchAllRelationshipRows(fetchPage);

    expect(rows).toHaveLength(120);
    expect(list.total_results).toBe(120);
    expect(list.summary.outgoing_count).toBe(120);
    expect(fetchPage).toHaveBeenCalledTimes(2);
    expect(fetchPage).toHaveBeenNthCalledWith(1, 0, RELATIONSHIP_FETCH_PAGE);
    expect(fetchPage).toHaveBeenNthCalledWith(2, 100, RELATIONSHIP_FETCH_PAGE);
  });
});
