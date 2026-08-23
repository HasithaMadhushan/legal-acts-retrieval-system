"use client";

import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export function PasswordField({
  id,
  label,
  value,
  onChange,
  visible,
  onToggle,
  placeholder = "Enter password",
  autoComplete,
  hint,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  visible: boolean;
  onToggle: () => void;
  placeholder?: string;
  autoComplete?: string;
  hint?: string;
}) {
  return (
    <Field>
      <div className="flex items-center justify-between gap-3">
        <FieldLabel htmlFor={id} className="text-xs tracking-[0.18em] uppercase text-muted-foreground">
          {label}
        </FieldLabel>
        <Button type="button" variant="link" size="sm" onClick={onToggle}>
          {visible ? "Hide password" : "Show password"}
        </Button>
      </div>
      <Input
        id={id}
        type={visible ? "text" : "password"}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        required
        className="h-10"
      />
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </Field>
  );
}
