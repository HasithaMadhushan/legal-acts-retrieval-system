import { describe, expect, it } from "vitest";
import {
  buildRelationshipDossier,
  dossierGroupKeyFromEdge,
  dossierKeyForAct,
  dossierNeighborCount,
  unresolvedTargetLabel
} from "../lib/relationship-dossier";
import type { RelationshipRow } from "../lib/types";

function row(overrides: Partial<RelationshipRow> & Pick<RelationshipRow, "id">): RelationshipRow {
  return {
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
    confidence_score: 0.92,
    raw_reference_text: "Goods and Services Tax Act",
    context_snippet: "as defined in the Goods and Services Tax Act",
    ...overrides
  };
}

describe("buildRelationshipDossier", () => {
  it("groups repeated outgoing citations to the same Act under Refers to", () => {
    const sections = buildRelationshipDossier(
      [
        row({ id: "a" }),
        row({ id: "b", source_section_number: "3" }),
        row({ id: "c", relationship_type: "CROSS_REFERENCE" })
      ],
      "vat"
    );

    expect(sections.map((section) => section.family)).toEqual(["refers"]);
    expect(sections[0]?.groups).toHaveLength(1);
    expect(sections[0]?.groups[0]?.count).toBe(3);
    expect(sections[0]?.groups[0]?.counterpartId).toBe("gst");
    expect(sections[0]?.groups[0]?.types).toEqual(["CROSS_REFERENCE", "REFERS_TO"]);
  });

  it("keeps amendment history separate from ordinary references", () => {
    const sections = buildRelationshipDossier(
      [
        row({ id: "a", relationship_type: "AMENDS", target_act_id: "ira", target_act_title: "Inland Revenue Act" }),
        row({ id: "b" })
      ],
      "vat"
    );

    expect(sections.map((section) => `${section.family}:${section.groups[0]?.count}`)).toEqual([
      "amends:1",
      "refers:1"
    ]);
  });

  it("lists incoming citations under Cited by, grouped by the source Act", () => {
    const sections = buildRelationshipDossier(
      [
        row({
          id: "in",
          source_act_id: "aca",
          source_act_title: "Anti-Corruption Act",
          target_act_id: "vat",
          target_act_title: "Value Added Tax Act",
          direction: "incoming"
        })
      ],
      "vat"
    );

    expect(sections[0]?.family).toBe("incoming");
    expect(sections[0]?.groups[0]?.counterpartId).toBe("aca");
    expect(sections[0]?.groups[0]?.counterpartLabel).toBe("Anti-Corruption Act");
  });

  it("puts self-maps in Within this Act and unmapped rows in Unresolved", () => {
    const sections = buildRelationshipDossier(
      [
        row({
          id: "self",
          target_act_id: "vat",
          target_act_title: "Value Added Tax Act",
          relationship_type: "CROSS_REFERENCE"
        }),
        row({
          id: "miss",
          mapped: false,
          target_act_id: null,
          target_act_title: null,
          target_act_title_raw: "Missing Act"
        })
      ],
      "vat"
    );

    expect(sections.map((section) => section.family)).toEqual(["internal", "unresolved"]);
    expect(sections[1]?.groups[0]?.counterpartLabel).toBe("Missing Act");
  });

  it("groups unresolved snippet citations under the cited Act name", () => {
    const sections = buildRelationshipDossier(
      [
        row({
          id: "a",
          mapped: false,
          target_act_id: null,
          target_act_title: null,
          target_act_title_raw: "means a director as defined in the Companies Act",
          raw_reference_text: "Companies Act"
        }),
        row({
          id: "b",
          mapped: false,
          target_act_id: null,
          target_act_title: null,
          target_act_title_raw: "shall have the meaning assigned to it by the Inland Revenue Act",
          raw_reference_text: "Inland Revenue Act"
        }),
        row({
          id: "c",
          mapped: false,
          target_act_id: null,
          target_act_title: null,
          target_act_title_raw: "in the Inland Revenue Act",
          raw_reference_text: "Inland Revenue Act"
        })
      ],
      "vat"
    );

    expect(sections[0]?.family).toBe("unresolved");
    expect(sections[0]?.groups.map((group) => `${group.counterpartLabel}:${group.count}`)).toEqual([
      "Inland Revenue Act:2",
      "Companies Act:1"
    ]);
  });
});

describe("unresolvedTargetLabel", () => {
  it("pulls a short Act name out of surrounding sentence fragments", () => {
    expect(
      unresolvedTargetLabel(
        row({
          id: "a",
          mapped: false,
          target_act_id: null,
          target_act_title_raw: "f goods and services to the mission of any State or any organization to which the provisions of the Diplomatic Privileges Act"
        })
      )
    ).toBe("Diplomatic Privileges Act");
  });

  it("keeps chapter citations and falls back when no Act name is present", () => {
    expect(
      unresolvedTargetLabel(
        row({
          id: "ch",
          mapped: false,
          target_act_id: null,
          target_act_title_raw: "Chapter 205",
          raw_reference_text: "Chapter 205"
        })
      )
    ).toBe("Chapter 205");
    expect(
      unresolvedTargetLabel(
        row({
          id: "miss",
          mapped: false,
          target_act_id: null,
          target_act_title: null,
          target_act_title_raw: null,
          raw_reference_text: "the said provision",
          target_act_number: null,
          target_act_year: null
        })
      )
    ).toBe("Unmatched target");
  });
});

describe("dossierNeighborCount", () => {
  it("counts distinct mapped Acts, ignoring self-maps and unresolved rows", () => {
    const sections = buildRelationshipDossier(
      [
        row({ id: "a" }),
        row({ id: "b", relationship_type: "AMENDS", target_act_id: "ira", target_act_title: "Inland Revenue Act" }),
        row({ id: "c", target_act_id: "vat", target_act_title: "Value Added Tax Act" }),
        row({ id: "d", mapped: false, target_act_id: null, target_act_title_raw: "Ghost" })
      ],
      "vat"
    );

    expect(dossierNeighborCount(sections)).toBe(2);
  });
});

describe("dossierKeyForAct", () => {
  it("opens the busiest group when one Act appears in more than one family", () => {
    const sections = buildRelationshipDossier(
      [
        row({ id: "a" }),
        row({ id: "b", source_section_number: "3" }),
        row({
          id: "c",
          relationship_type: "AMENDS",
          target_act_id: "gst",
          target_act_title: "Goods and Services Tax Act"
        })
      ],
      "vat"
    );

    expect(dossierKeyForAct(sections, "gst")).toBe("refers|gst");
  });
});

describe("dossierGroupKeyFromEdge", () => {
  it("opens the Refers to group for an outgoing citation line", () => {
    expect(
      dossierGroupKeyFromEdge("vat", { source: "vat", target: "gst", label: "REFERS_TO" })
    ).toBe("refers|gst");
  });

  it("opens Cited by for an incoming citation line", () => {
    expect(
      dossierGroupKeyFromEdge("vat", { source: "aca", target: "vat", label: "REFERS_TO" })
    ).toBe("incoming|aca");
  });
});
