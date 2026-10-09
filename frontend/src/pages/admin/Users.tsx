import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { FileUp, GraduationCap, Search, UserPlus } from "lucide-react";
import { EmptyState, ErrorState, PageLoader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { api, qs } from "@/lib/api";
import type { AdminUser, Page } from "@/types";
import { PageHeader, Pagination, RoleBadge, StatusBadge, Table, formatDate, useLookups } from "./common";

const PAGE_SIZE = 25;
const FILTERS = ["q", "role", "status", "class_id", "subject_id", "created_from", "created_to"] as const;

function assignmentSummary(u: AdminUser): string {
  if (u.role === "student") return u.class?.name ?? "Not in a class";
  if (u.role !== "teacher") return "—";
  const parts = [
    ...u.homeroom.map((c) => `Class teacher ${c.name}`),
    ...u.teaching.map((t) => `${t.subject.name} · ${t.class.name}`),
  ];
  return parts.length ? parts.join(", ") : "No assignments";
}

export default function UsersPage() {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? 1);
  const filters = Object.fromEntries(FILTERS.map((k) => [k, params.get(k) ?? ""])) as Record<(typeof FILTERS)[number], string>;
  const [search, setSearch] = useState(filters.q);
  const lookups = useLookups();

  useEffect(() => setSearch(filters.q), [filters.q]);

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    next.delete("page");
    setParams(next, { replace: true });
  };

  const { data, error, isPending, isFetching, refetch } = useQuery({
    queryKey: ["admin", "users", filters, page],
    queryFn: () => api.get<Page<AdminUser>>(`/api/admin/users${qs({ ...filters, page, page_size: PAGE_SIZE })}`),
    placeholderData: keepPreviousData,
  });

  const filtered = FILTERS.some((k) => filters[k]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Users"
        description="Students, teachers and administrators in your school."
        actions={
          <>
            <Button asChild variant="outline">
              <Link to="/admin/users/import">
                <FileUp /> Import CSV
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/admin/users/new?role=teacher">
                <UserPlus /> Add teacher
              </Link>
            </Button>
            <Button asChild>
              <Link to="/admin/users/new?role=student">
                <GraduationCap /> Add student
              </Link>
            </Button>
          </>
        }
      />

      <Card className="gap-3">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setFilter("q", search.trim());
          }}
          role="search"
        >
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name, email, username or ID" aria-label="Search users" />
          <Button type="submit" variant="secondary">
            <Search /> Search
          </Button>
        </form>
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <div className="space-y-1.5">
            <Label htmlFor="f-role">Role</Label>
            <Select id="f-role" value={filters.role} onChange={(e) => setFilter("role", e.target.value)}>
              <option value="">All roles</option>
              <option value="student">Students</option>
              <option value="teacher">Teachers</option>
              <option value="admin">Admins</option>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="f-status">Status</Label>
            <Select id="f-status" value={filters.status} onChange={(e) => setFilter("status", e.target.value)}>
              <option value="">Any status</option>
              <option value="active">Active</option>
              <option value="disabled">Disabled</option>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="f-class">Class</Label>
            <Select id="f-class" value={filters.class_id} onChange={(e) => setFilter("class_id", e.target.value)}>
              <option value="">Any class</option>
              {lookups.data?.classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.academic_year})
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="f-subject">Subject</Label>
            <Select id="f-subject" value={filters.subject_id} onChange={(e) => setFilter("subject_id", e.target.value)}>
              <option value="">Any subject</option>
              {lookups.data?.subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="f-from">Created from</Label>
            <Input id="f-from" type="date" value={filters.created_from} onChange={(e) => setFilter("created_from", e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="f-to">Created to</Label>
            <Input id="f-to" type="date" value={filters.created_to} onChange={(e) => setFilter("created_to", e.target.value)} />
          </div>
        </div>
        {filtered && (
          <Button variant="link" className="h-auto w-fit p-0" onClick={() => setParams({}, { replace: true })}>
            Clear filters
          </Button>
        )}
      </Card>

      {isPending ? (
        <PageLoader rows={0} />
      ) : error || !data ? (
        <ErrorState message={error?.message ?? "Could not load users"} onRetry={() => refetch()} />
      ) : data.items.length === 0 ? (
        <EmptyState emoji="🔎" title="No matching users" description={filtered ? "Try different filters." : "Add a student or teacher to get started."} />
      ) : (
        <Card className="gap-0 overflow-hidden p-0">
          <Table head={["Name", "Role", "ID", "Class / teaching", "Status", "Created", "Last sign-in"]} busy={isFetching}>
            {data.items.map((u) => (
              <tr key={u.id} className="align-top">
                <td className="px-4 py-3">
                  <Link to={`/admin/users/${u.id}`} className="font-semibold text-primary hover:underline">
                    {u.full_name}
                  </Link>
                  <span className="block text-xs text-muted-foreground">{u.username ? `${u.username} · ${u.email}` : u.email}</span>
                </td>
                <td className="px-4 py-3">
                  <RoleBadge role={u.role} />
                </td>
                <td className="px-4 py-3 whitespace-nowrap">{u.student_number ?? u.staff_number ?? "—"}</td>
                <td className="max-w-xs px-4 py-3 text-muted-foreground">{assignmentSummary(u)}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={u.status} />
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-muted-foreground">{formatDate(u.created_at)}</td>
                <td className="px-4 py-3 whitespace-nowrap text-muted-foreground">{u.last_login_at ? formatDate(u.last_login_at) : "Never"}</td>
              </tr>
            ))}
          </Table>
          <Pagination
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            busy={isFetching}
            onPage={(p) => {
              const next = new URLSearchParams(params);
              next.set("page", String(p));
              setParams(next, { replace: true });
            }}
          />
        </Card>
      )}
    </div>
  );
}
