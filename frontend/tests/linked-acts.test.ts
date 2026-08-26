import { describe, expect, it } from "vitest";
import { aggregateGraphEdges } from "../lib/graph-edges";
import { summarizeLinkedActs } from "../lib/linked-acts";

describe("summarizeLinkedActs", () => {
  it("groups graph edges by the other Act and sums citation counts", () => {
    const edges = aggregateGraphEdges([
      { id: "a", source: "vat", target: "gst", label: "REFERS_TO", status: "VERIFIED" },
      { id: "b", source: "vat", target: "gst", label: "REFERS_TO", status: "VERIFIED" },
      { id: "c", source: "vat", target: "gst", label: "CROSS_REFERENCE", status: "PENDING" },
      { id: "d", source: "vat", target: "ira", label: "AMENDS", status: "VERIFIED" }
    ]);
    const linked = summarizeLinkedActs(
      edges,
      [
        { id: "vat", label: "Value Added Tax Act" },
        { id: "gst", label: "Goods and Services Tax Act" },
        { id: "ira", label: "Inland Revenue Act" }
      ],
      "vat"
    );

    expect(linked).toEqual([
      {
        actId: "gst",
        title: "Goods and Services Tax Act",
        total: 3,
        pending: true,
        types: [
          { type: "REFERS_TO", count: 2, pending: false },
          { type: "CROSS_REFERENCE", count: 1, pending: true }
        ]
      },
      {
        actId: "ira",
        title: "Inland Revenue Act",
        total: 1,
        pending: false,
        types: [{ type: "AMENDS", count: 1, pending: false }]
      }
    ]);
  });

  it("ignores edges that do not touch the focus Act", () => {
    const edges = aggregateGraphEdges([
      { id: "a", source: "gst", target: "ira", label: "REFERS_TO", status: "VERIFIED" }
    ]);
    expect(summarizeLinkedActs(edges, [{ id: "vat", label: "VAT" }], "vat")).toEqual([]);
  });
});
