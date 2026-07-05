"use client";

import { LEGAL_DISCLAIMER } from "@/lib/types";

export function LegalDisclaimer() {
  return (
    <aside className="disclaimer" role="note">
      <strong>Legal disclaimer:</strong> {LEGAL_DISCLAIMER}
    </aside>
  );
}
