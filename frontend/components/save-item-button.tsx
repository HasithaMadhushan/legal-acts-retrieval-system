"use client";

import { useEffect, useState } from "react";
import { createSavedItem, deleteSavedItem, listSavedItems } from "@/lib/api";
import { getStoredRole } from "@/lib/auth";
import type { Role, SavedItem, SavedItemCreatePayload } from "@/lib/types";

export function SaveItemButton({
  payload,
  label = "Save to workspace"
}: {
  payload: SavedItemCreatePayload;
  label?: string;
}) {
  const [role, setRole] = useState<Role | null>(null);
  const [savedItemId, setSavedItemId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const storedRole = getStoredRole();
    setRole(storedRole);
    if (storedRole === "ADMIN" || storedRole === "LAWYER") {
      void refreshSavedState();
    }
  }, [payload.item_type, payload.act_id, payload.section_id, payload.reference_id]);

  async function refreshSavedState() {
    try {
      const response = await listSavedItems({
        item_type: payload.item_type,
        limit: "100",
        offset: "0"
      });
      const match = response.items.find((item) => matchesPayload(item, payload));
      setSavedItemId(match?.id ?? null);
    } catch {
      setSavedItemId(null);
    }
  }

  async function toggleSaved() {
    setLoading(true);
    setMessage("");
    try {
      if (savedItemId) {
        await deleteSavedItem(savedItemId);
        setSavedItemId(null);
        setMessage("Removed from workspace.");
      } else {
        const saved = await createSavedItem(payload);
        setSavedItemId(saved.id);
        setMessage("Saved to workspace.");
      }
    } catch (err) {
      const text = err instanceof Error ? err.message : "Workspace action failed.";
      setMessage(text.includes("already saved") ? "Already saved in workspace." : text);
      await refreshSavedState();
    } finally {
      setLoading(false);
    }
  }

  if (role !== "ADMIN" && role !== "LAWYER") return null;

  return (
    <div className="toolbar">
      <button type="button" className="secondary" onClick={toggleSaved} disabled={loading}>
        {loading ? "Saving..." : savedItemId ? "Unsave from workspace" : label}
      </button>
      {message ? <span className="muted">{message}</span> : null}
    </div>
  );
}

function matchesPayload(item: SavedItem, payload: SavedItemCreatePayload) {
  if (payload.item_type !== item.item_type) return false;
  if (payload.item_type === "ACT") return item.act_id === payload.act_id;
  if (payload.item_type === "SECTION") return item.section_id === payload.section_id;
  return item.reference_id === payload.reference_id;
}
