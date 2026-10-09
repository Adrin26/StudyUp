import { z } from "zod";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Select } from "@/components/ui/input";
import type { AdminLookups } from "@/types";

/** Mirrors the backend rules in schemas.py; the server validates again. */
export const identityFields = {
  full_name: z.string().trim().min(2, "Enter the full name.").max(200),
  email: z.string().trim().email("Enter a valid email address."),
  username: z
    .string()
    .trim()
    .regex(/^([a-zA-Z0-9][a-zA-Z0-9._-]{2,59})?$/, "3–60 letters, numbers, dots, dashes or underscores."),
  id_number: z
    .string()
    .trim()
    .min(1, "Required.")
    .regex(/^[A-Za-z0-9][A-Za-z0-9/-]{0,29}$/, "Up to 30 letters, numbers, '/' or '-'."),
  form: z.string(),
  department: z.string().trim().max(100),
};

export function SubjectPicker({ subjects, value, onChange }: { subjects: AdminLookups["subjects"]; value: string[]; onChange: (ids: string[]) => void }) {
  return (
    <div className="grid gap-1 rounded-xl border p-2 sm:grid-cols-2">
      {subjects.map((s) => (
        <label key={s.id} className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-muted">
          <Checkbox checked={value.includes(s.id)} onCheckedChange={() => onChange(value.includes(s.id) ? value.filter((i) => i !== s.id) : [...value, s.id])} />
          {s.name}
        </label>
      ))}
    </div>
  );
}

export interface PairDraft {
  subject_id: string;
  class_id: string;
}

export function AssignmentRows({ lookups, value, onChange }: { lookups: AdminLookups; value: PairDraft[]; onChange: (rows: PairDraft[]) => void }) {
  const update = (i: number, patch: Partial<PairDraft>) => onChange(value.map((row, j) => (j === i ? { ...row, ...patch } : row)));
  return (
    <div className="space-y-2">
      {value.length === 0 && <p className="text-sm text-muted-foreground">No subjects yet. You can also assign them later from Teaching assignments.</p>}
      {value.map((row, i) => (
        <div key={i} className="flex gap-2">
          <Select aria-label={`Subject ${i + 1}`} value={row.subject_id} onChange={(e) => update(i, { subject_id: e.target.value })}>
            <option value="">Subject…</option>
            {lookups.subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
          <Select aria-label={`Class ${i + 1}`} value={row.class_id} onChange={(e) => update(i, { class_id: e.target.value })}>
            <option value="">Class…</option>
            {lookups.classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.academic_year})
              </option>
            ))}
          </Select>
          <Button type="button" variant="ghost" size="icon" aria-label={`Remove row ${i + 1}`} onClick={() => onChange(value.filter((_, j) => j !== i))}>
            <Trash2 />
          </Button>
        </div>
      ))}
      <Button type="button" variant="outline" size="sm" onClick={() => onChange([...value, { subject_id: "", class_id: "" }])}>
        <Plus /> Add subject and class
      </Button>
    </div>
  );
}
