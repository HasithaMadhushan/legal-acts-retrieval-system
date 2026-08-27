import { describe, expect, it } from "vitest";
import {
  aggregateGraphEdges,
  displayEdgeLabel,
  edgeStrokeWidth,
  graphModelFromRows,
  neighborCount,
  rowsMatchingGraphSelection,
  withPairOffsets,
  type GraphActRow
} from "../lib/graph-edges";

const vatToGst = {
  source: "vat",
  target: "gst",
  label: "REFERS_TO",
  count: 1
};

describe("aggregateGraphEdges", () => {
  it("collapses repeated citations between the same Acts into one weighted edge", () => {
    const aggregated = aggregateGraphEdges([
      { id: "a", source: "vat", target: "gst", label: "REFERS_TO", status: "VERIFIED" },
      { id: "b", source: "vat", target: "gst", label: "REFERS_TO", status: "VERIFIED" },
      { id: "c", source: "vat", target: "gst", label: "REFERS_TO", status: "VERIFIED" }
    ]);

    expect(aggregated).toEqual([
      {
        key: "vat|gst|REFERS_TO",
        source: "vat",
        target: "gst",
        label: "REFERS_TO",
        count: 3,
        pending: false,
        memberIds: ["a", "b", "c"]
      }
    ]);
  });

  it("keeps different relationship types between the same Acts as separate edges", () => {
    const aggregated = aggregateGraphEdges([
      { id: "a", source: "vat", target: "gst", label: "REFERS_TO", status: "VERIFIED" },
      { id: "b", source: "vat", target: "gst", label: "AMENDS", status: "VERIFIED" }
    ]);

    expect(aggregated.map((edge) => `${edge.label}:${edge.count}`)).toEqual([
      "REFERS_TO:1",
      "AMENDS:1"
    ]);
  });

  it("skips self-maps so they never become graph lines", () => {
    const aggregated = aggregateGraphEdges([
      { id: "loop", source: "vat", target: "vat", label: "REFERS_TO", status: "VERIFIED" },
      { id: "out", source: "vat", target: "gst", label: "REFERS_TO", status: "VERIFIED" }
    ]);

    expect(aggregated).toHaveLength(1);
    expect(aggregated[0]?.source).toBe("vat");
    expect(aggregated[0]?.target).toBe("gst");
  });

  it("marks an aggregated edge pending when any member is not verified", () => {
    const aggregated = aggregateGraphEdges([
      { id: "a", source: "vat", target: "gst", label: "REFERS_TO", status: "VERIFIED" },
      { id: "b", source: "vat", target: "gst", label: "REFERS_TO", status: "PENDING" }
    ]);

    expect(aggregated[0]?.pending).toBe(true);
    expect(aggregated[0]?.count).toBe(2);
  });
});

describe("neighborCount", () => {
  it("counts distinct neighboring Acts, not raw citation rows", () => {
    const edges = aggregateGraphEdges([
      { id: "a", source: "vat", target: "gst", label: "REFERS_TO", status: "VERIFIED" },
      { id: "b", source: "vat", target: "gst", label: "AMENDS", status: "VERIFIED" },
      { id: "c", source: "vat", target: "ira", label: "REFERS_TO", status: "VERIFIED" }
    ]);

    expect(neighborCount("vat", edges)).toBe(2);
    expect(neighborCount("gst", edges)).toBe(1);
  });
});

describe("displayEdgeLabel", () => {
  it("shows the relationship type and citation count", () => {
    expect(displayEdgeLabel("REFERS_TO", 72)).toBe("refers to · 72");
    expect(displayEdgeLabel("AMENDS", 1)).toBe("amends · 1");
  });
});

describe("edgeStrokeWidth", () => {
  it("grows with citation count and caps at 8", () => {
    expect(edgeStrokeWidth(1)).toBe(1.75);
    expect(edgeStrokeWidth(2)).toBe(3.1);
    expect(edgeStrokeWidth(1024)).toBe(8);
  });
});

describe("withPairOffsets", () => {
  it("fans multiple types between the same Acts off the shared centre line", () => {
    const offset = withPairOffsets([
      {
        key: "vat|gst|REFERS_TO",
        source: "vat",
        target: "gst",
        label: "REFERS_TO",
        count: 72,
        pending: false,
        memberIds: ["a"]
      },
      {
        key: "vat|gst|AMENDS",
        source: "vat",
        target: "gst",
        label: "AMENDS",
        count: 3,
        pending: false,
        memberIds: ["b"]
      }
    ]);

    expect(offset.map((edge) => edge.pairOffset)).toEqual([-0.5, 0.5]);
  });
});

describe("rowsMatchingGraphSelection", () => {
  const rows = [
    { id: "1", source_act_id: "vat", target_act_id: "gst", relationship_type: "REFERS_TO" },
    { id: "2", source_act_id: "vat", target_act_id: "gst", relationship_type: "AMENDS" },
    { id: "3", source_act_id: "ira", target_act_id: "vat", relationship_type: "REFERS_TO" }
  ];

  it("lists only citations for a selected Act-to-Act link", () => {
    expect(rowsMatchingGraphSelection(rows, { edge: vatToGst, nodeId: "gst" }).map((row) => row.id)).toEqual([
      "1"
    ]);
  });

  it("lists every citation involving a selected node when no link is selected", () => {
    expect(rowsMatchingGraphSelection(rows, { edge: null, nodeId: "vat" }).map((row) => row.id)).toEqual([
      "1",
      "2",
      "3"
    ]);
  });
});

describe("graphModelFromRows", () => {
  it("turns every mapped cross-Act citation into a graph edge, including past the old 100-row cap", () => {
    const rows: GraphActRow[] = Array.from({ length: 120 }, (_, index) => ({
      id: `cite-${index}`,
      source_act_id: "vat",
      source_act_title: "Value Added Tax Act",
      target_act_id: "gst",
      target_act_title: "Goods and Services Tax Act",
      relationship_type: "REFERS_TO",
      verification_status: index === 0 ? "PENDING" : "VERIFIED",
      mapped: true
    }));
    rows.push({
      id: "self",
      source_act_id: "vat",
      source_act_title: "Value Added Tax Act",
      target_act_id: "vat",
      target_act_title: "Value Added Tax Act",
      relationship_type: "REFERS_TO",
      verification_status: "VERIFIED",
      mapped: true
    });
    rows.push({
      id: "unresolved",
      source_act_id: "vat",
      source_act_title: "Value Added Tax Act",
      target_act_id: null,
      target_act_title: null,
      relationship_type: "REFERS_TO",
      verification_status: "NEEDS_REVIEW",
      mapped: false
    });

    const model = graphModelFromRows(rows);
    const aggregated = aggregateGraphEdges(model.edges);

    expect(model.edges).toHaveLength(120);
    expect(aggregated).toEqual([
      {
        key: "vat|gst|REFERS_TO",
        source: "vat",
        target: "gst",
        label: "REFERS_TO",
        count: 120,
        pending: true,
        memberIds: rows.slice(0, 120).map((row) => row.id)
      }
    ]);
    expect(model.nodes.map((node) => node.id).sort()).toEqual(["gst", "vat"]);
  });
});
