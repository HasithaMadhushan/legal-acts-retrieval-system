import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { describeSearchMode, type SearchResponse } from "../lib/types";

function modeResponse(overrides: Partial<SearchResponse> = {}): SearchResponse {
  return {
    query: "jurisdiction",
    results: [],
    total_results: 0,
    act_results: 0,
    section_results: 0,
    reference_results: 0,
    limit: 25,
    offset: 0,
    disclaimer: "",
    requested_mode: "all",
    effective_mode: "keyword",
    embedding_model: "sentence-transformers/all-MiniLM-L6-v2",
    semantic_ready: false,
    ...overrides
  };
}

describe("search mode metadata", () => {
  it("does not describe all-mode keyword fallback as hybrid", () => {
    expect(describeSearchMode(modeResponse())).toBe("using keyword search (requested all)");
  });

  it("describes hybrid when all-mode search is semantically ready", () => {
    expect(
      describeSearchMode(
        modeResponse({
          effective_mode: "hybrid",
          semantic_ready: true
        })
      )
    ).toBe("using hybrid search");
  });

  it("describes keyword mode without claiming hybrid", () => {
    expect(
      describeSearchMode(modeResponse({ requested_mode: "keyword", effective_mode: "keyword" }))
    ).toBe("using keyword search");
  });

  it("describes semantic mode without claiming hybrid", () => {
    expect(
      describeSearchMode(
        modeResponse({
          requested_mode: "semantic",
          effective_mode: "semantic",
          semantic_ready: true
        })
      )
    ).toBe("using semantic search");
  });

  it("public and lawyer search pages surface requested and effective mode", () => {
    const searchPage = readFileSync("app/search/page.tsx", "utf8");
    const lawyerSearchPage = readFileSync("app/lawyer/search/page.tsx", "utf8");
    expect(searchPage).toContain("describeSearchMode");
    expect(searchPage).toContain("semantic_ready");
    expect(searchPage).toContain("embedding_model");
    expect(searchPage).toContain("searchErrorMessage");
    expect(lawyerSearchPage).toContain("describeSearchMode");
    expect(lawyerSearchPage).toContain("search_mode");
    expect(lawyerSearchPage).toContain("searchErrorMessage");
    expect(searchPage).toContain('label: "Hybrid"');
    expect(searchPage).toContain("Combines exact keyword matches with meaning-based section retrieval");
    expect(lawyerSearchPage).toContain('if (value === "all") return "Hybrid"');
  });

  it("maps unavailable semantic-only errors to stable copy", () => {
    const api = readFileSync("lib/api.ts", "utf8");
    expect(api).toContain("export function searchErrorMessage");
    expect(api).toContain("Semantic search is not enabled yet. Use Keyword or Hybrid.");
    expect(api).toContain("Semantic search is enabled but not ready. Use Keyword or Hybrid.");
    expect(api).toContain("status === 400");
    expect(api).toContain("status === 503");
  });

  it("global search still navigates into the public search page query string", () => {
    const globalSearch = readFileSync("components/lexatlas/global-search.tsx", "utf8");
    expect(globalSearch).toContain("`/search?q=${encodeURIComponent(trimmed)}`");
    expect(globalSearch).not.toContain("search(");
  });
});
