"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

type ConfirmDialogProps = Readonly<{
  title: string;
  description: string;
  confirmLabel?: string;
  pendingLabel?: string;
  pending?: boolean;
  onConfirm: () => void | Promise<void>;
  triggerLabel: string;
  triggerClassName?: string;
}>;

export function ConfirmDialog({
  title,
  description,
  confirmLabel = "Confirm",
  pendingLabel = "Working...",
  pending = false,
  onConfirm,
  triggerLabel,
  triggerClassName
}: ConfirmDialogProps) {
  const [open, setOpen] = useState(false);

  async function confirm() {
    await onConfirm();
    setOpen(false);
  }

  return (
    <>
      <Button type="button" variant="outline" className={triggerClassName} onClick={() => setOpen(true)}>
        {triggerLabel}
      </Button>
      {open ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-sm border border-border bg-card p-5 shadow-lg">
            <h2 className="font-serif text-xl font-semibold">{title}</h2>
            <p className="mt-2 text-sm text-muted-foreground">{description}</p>
            <div className="mt-4 flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)} disabled={pending}>
                Cancel
              </Button>
              <Button type="button" onClick={() => void confirm()} disabled={pending}>
                {pending ? pendingLabel : confirmLabel}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
