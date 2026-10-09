import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { EmptyState, ErrorState, PageLoader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label, Select } from "@/components/ui/input";
import { api, qs } from "@/lib/api";
import type { AuditEntry } from "@/types";
import { actionLabel, formatWhen } from "./audit";

interface AuditPage {
  items: AuditEntry[];
  total: number;
  page: number;
  page_size: number;
  actions: string[];
}

const PAGE_SIZE = 25;

function describe(details: Record<string, unknown>): string {
  return Object.entries(details)
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${String(v)}`)
    .join(" · ");
}

export default function AuditLogPage() {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const { data, error, isPending, isFetching, refetch } = useQuery({
    queryKey: ["admin", "audit", page, action],
    queryFn: () => api.get<AuditPage>(`/api/admin/audit-logs${qs({ page, page_size: PAGE_SIZE, action })}`),
    placeholderData: keepPreviousData,
  });

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">Audit log</h1>
          <p className="text-muted-foreground">Significant account and administrative actions. Passwords and tokens are never recorded.</p>
        </div>
        <div className="w-full space-y-1.5 sm:w-64">
          <Label htmlFor="action-filter">Action</Label>
          <Select
            id="action-filter"
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All actions</option>
            {data?.actions.map((a) => (
              <option key={a} value={a}>
                {actionLabel(a)}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {isPending ? (
        <PageLoader rows={0} />
      ) : error || !data ? (
        <ErrorState message={error?.message ?? "Could not load"} onRetry={() => refetch()} />
      ) : data.items.length === 0 ? (
        <EmptyState emoji="📜" title="No matching entries" description="Actions such as account creation and password resets will appear here." />
      ) : (
        <Card className="gap-0 overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/60 text-xs font-semibold uppercase text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-3">When</th>
                  <th scope="col" className="px-4 py-3">Action</th>
                  <th scope="col" className="px-4 py-3">By</th>
                  <th scope="col" className="px-4 py-3">Details</th>
                </tr>
              </thead>
              <tbody className={`divide-y ${isFetching ? "opacity-60" : ""}`}>
                {data.items.map((e) => (
                  <tr key={e.id} className="align-top">
                    <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">{formatWhen(e.created_at)}</td>
                    <td className="px-4 py-3 font-semibold">{actionLabel(e.action)}</td>
                    <td className="px-4 py-3">{e.actor ? `${e.actor.name} (${e.actor.role})` : "System"}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {describe(e.details) || "—"}
                      {e.ip_address && <span className="block text-xs">IP {e.ip_address}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between border-t px-4 py-3 text-sm">
            <span className="text-muted-foreground">
              {data.total} entr{data.total === 1 ? "y" : "ies"} · page {data.page} of {pages}
            </span>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page">
                <ChevronLeft /> Previous
              </Button>
              <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage((p) => p + 1)} aria-label="Next page">
                Next <ChevronRight />
              </Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
