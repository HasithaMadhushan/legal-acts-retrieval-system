"use client";

import { useEffect } from "react";
import { getToken } from "@/lib/auth";
import { recordReadingHistory } from "@/lib/api";

export function useRecordReading(payload: {
  item_type: "ACT" | "SECTION";
  act_id: string;
  section_id?: string | null;
}) {
  useEffect(() => {
    if (!getToken() || !payload.act_id) return;
    recordReadingHistory(payload).catch(() => {
      // Reading history is best-effort and should not block page render.
    });
  }, [payload.act_id, payload.item_type, payload.section_id]);
}
