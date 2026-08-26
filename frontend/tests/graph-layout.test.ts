import { describe, expect, it } from "vitest";
import {
  clampNodePosition,
  clientPointToGraph,
  defaultNodePosition,
  dragNodePosition,
  GRAPH_VIEW,
  resolvedNodePosition
} from "../lib/graph-layout";

const nodes = [{ id: "vat" }, { id: "gst" }, { id: "ira" }];

describe("defaultNodePosition", () => {
  it("places the focus Act in the centre slot", () => {
    expect(defaultNodePosition("vat", nodes, "vat")).toEqual({ x: 376, y: 252 });
  });

  it("places neighbors in the surrounding slots", () => {
    expect(defaultNodePosition("gst", nodes, "vat")).toEqual({ x: 126, y: 236 });
    expect(defaultNodePosition("ira", nodes, "vat")).toEqual({ x: 610, y: 212 });
  });
});

describe("resolvedNodePosition", () => {
  it("uses a dragged override instead of the default slot", () => {
    expect(
      resolvedNodePosition("gst", nodes, "vat", { gst: { x: 400, y: 300 } })
    ).toEqual({ x: 400, y: 300 });
  });
});

describe("clampNodePosition", () => {
  it("keeps the Act card fully inside the canvas", () => {
    expect(clampNodePosition({ x: 0, y: 0 })).toEqual({ x: 90, y: 42 });
    expect(clampNodePosition({ x: 900, y: 700 })).toEqual({
      x: GRAPH_VIEW.width - 90,
      y: GRAPH_VIEW.height - 42
    });
  });
});

describe("clientPointToGraph", () => {
  const svg = { left: 0, top: 0, width: 784, height: 560 };

  it("maps the canvas centre to graph coordinates at zoom 1", () => {
    expect(clientPointToGraph({ x: 392, y: 280 }, svg, 1)).toEqual({ x: 392, y: 280 });
  });

  it("undoes the centre-based zoom transform", () => {
    expect(clientPointToGraph({ x: 392, y: 280 }, svg, 2)).toEqual({ x: 392, y: 280 });
  });
});

describe("dragNodePosition", () => {
  it("moves the node by the pointer minus the grab offset", () => {
    const svg = { left: 0, top: 0, width: 784, height: 560 };
    expect(
      dragNodePosition({ x: 200, y: 180 }, svg, 1, { x: 10, y: 20 })
    ).toEqual({ x: 190, y: 160 });
  });
});
