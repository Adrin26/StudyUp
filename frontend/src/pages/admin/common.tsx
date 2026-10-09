import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ChevronLeft, ChevronRight } from "lucide-react";
import { FormAlert } from "@/components/form";
import { Spinner } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { queryClient } from "@/lib/query";
import type { AccountStatus, AdminLookups, Role } from "@/types";

export function PageHeader({ title, description, actions, back }: { title: string; description?: ReactNode; actions?: ReactNode; back?: { to: string; label: string } }) {
  return (
    <div className="space-y-2">
      {back && (
        <Link to={back.to} className="inline-flex items-center gap-1 text-sm font-semibold text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" /> {back.label}
        </Link>
      )}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{title}</h1>
          {description && <p className="text-muted-foreground">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
    </div>
  );
}

export function Pagination({ page, pageSize, total, onPage, busy }: { page: number; pageSize: number; total: number; onPage: (p: number) => void; busy?: boolean }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center justify-between border-t px-4 py-3 text-sm">
      <span className="text-muted-foreground">
        {total} result{total === 1 ? "" : "s"} · page {page} of {pages}
      </span>
      <div className="flex gap-2">
        <Button size="sm" variant="outline" disabled={busy || page <= 1} onClick={() => onPage(page - 1)}>
          <ChevronLeft /> Previous
        </Button>
        <Button size="sm" variant="outline" disabled={busy || page >= pages} onClick={() => onPage(page + 1)}>
          Next <ChevronRight />
        </Button>
      </div>
    </div>
  );
}

export const ROLE_LABEL: Record<Role, string> = { admin: "Admin", teacher: "Teacher", student: "Student" };

export function RoleBadge({ role }: { role: Role }) {
  return <Badge variant={role === "admin" ? "default" : "secondary"}>{ROLE_LABEL[role]}</Badge>;
}

export function StatusBadge({ status }: { status: AccountStatus | "archived" }) {
  if (status === "active") return <Badge variant="success">Active</Badge>;
  return <Badge variant="danger">{status === "disabled" ? "Disabled" : "Archived"}</Badge>;
}

export function formatDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" }) : "—";
}

export function errorText(e: unknown, fallback = "Something went wrong"): string {
  return e instanceof Error ? e.message : fallback;
}

export function useLookups() {
  return useQuery({ queryKey: ["admin", "lookups"], queryFn: () => api.get<AdminLookups>("/api/admin/lookups") });
}

/** Admin data is interlinked (users, classes, counts), so refresh every admin query after a change. */
export function refreshAdmin() {
  return queryClient.invalidateQueries({ queryKey: ["admin"] });
}

export function ConfirmButton({
  trigger,
  title,
  description,
  confirmLabel,
  destructive,
  onConfirm,
}: {
  trigger: (open: () => void) => ReactNode;
  title: string;
  description: ReactNode;
  confirmLabel: string;
  destructive?: boolean;
  onConfirm: () => Promise<unknown>;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
      setOpen(false);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {trigger(() => setOpen(true))}
      <Dialog open={open} onOpenChange={(o) => !busy && setOpen(o)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription asChild>
              <div>{description}</div>
            </DialogDescription>
          </DialogHeader>
          {error && <FormAlert>{error}</FormAlert>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setOpen(false)} disabled={busy}>
              Cancel
            </Button>
            <Button variant={destructive ? "destructive" : "default"} onClick={confirm} disabled={busy}>
              {busy && <Spinner />} {confirmLabel}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

export function Table({ head, children, busy }: { head: string[]; children: ReactNode; busy?: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="bg-muted/60 text-xs font-semibold uppercase text-muted-foreground">
          <tr>
            {head.map((h) => (
              <th key={h} scope="col" className="px-4 py-3 whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className={`divide-y ${busy ? "opacity-60" : ""}`}>{children}</tbody>
      </table>
    </div>
  );
}
