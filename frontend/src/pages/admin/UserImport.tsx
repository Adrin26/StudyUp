import { useState, type ChangeEvent } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Download, FileUp, Upload, XCircle } from "lucide-react";
import { FormAlert } from "@/components/form";
import { Spinner } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ImportPreview, ImportResult } from "@/types";
import { PageHeader, Table, errorText, refreshAdmin } from "./common";

const MAX_BYTES = 500_000;
const COLUMNS: [string, string][] = [
  ["role", "Required. student or teacher"],
  ["full_name", "Required"],
  ["email", "Required. Must be unique"],
  ["username", "Optional. Taken from the email if blank"],
  ["student_number", "Required for students"],
  ["staff_number", "Required for teachers"],
  ["form", "Optional, 1–5 (students)"],
  ["class", "Optional class name in the current academic year (students)"],
  ["department", "Optional (teachers)"],
];
const TEMPLATE = `${COLUMNS.map(([c]) => c).join(",")}\nstudent,Nur Aina Binti Ahmad,aina@example.edu.my,,S260101,,4,4 Bestari,\nteacher,Encik Hafiz Rahman,hafiz@example.edu.my,,,T2001,,,Science\n`;

export default function UserImportPage() {
  const { usesSupabase } = useAuth();
  const [fileName, setFileName] = useState<string | null>(null);
  const [csv, setCsv] = useState<string | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [sendInvites, setSendInvites] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const templateUrl = `data:text/csv;charset=utf-8,${encodeURIComponent(TEMPLATE)}`;

  const choose = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    setPreview(null);
    setResult(null);
    setError(null);
    if (!file) return;
    if (file.size > MAX_BYTES) {
      setError("That file is larger than 500 KB. Split it into smaller files.");
      return;
    }
    setBusy(true);
    try {
      const text = await file.text();
      setFileName(file.name);
      setCsv(text);
      setPreview(await api.post<ImportPreview>("/api/admin/users/import/preview", { csv: text }));
    } catch (err) {
      setError(errorText(err, "Could not read the file"));
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    if (!csv) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await api.post<ImportResult>("/api/admin/users/import/confirm", { csv, send_invites: sendInvites }));
      setPreview(null);
      await refreshAdmin();
    } catch (err) {
      setError(errorText(err, "Import failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Import users" back={{ to: "/admin/users", label: "Users" }} description="Create student and teacher accounts from a CSV file. Nothing is created until you review the preview and confirm." />
      {usesSupabase && <FormAlert tone="info">Importing is not available while sign-in is handled by Supabase.</FormAlert>}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>1. Choose a CSV file</CardTitle>
            <CardDescription>UTF-8, first row is the header, at most 500 rows.</CardDescription>
          </CardHeader>
          <div className="flex flex-wrap items-center gap-3">
            <Button asChild disabled={busy || usesSupabase}>
              <label className="cursor-pointer">
                {busy ? <Spinner /> : <Upload />} Choose file
                <input type="file" accept=".csv,text/csv" className="sr-only" onChange={choose} disabled={busy || usesSupabase} />
              </label>
            </Button>
            <Button asChild variant="outline">
              <a href={templateUrl} download="minda-users-template.csv">
                <Download /> Download template
              </a>
            </Button>
            {fileName && <span className="text-sm text-muted-foreground">{fileName}</span>}
          </div>
          {error && <FormAlert>{error}</FormAlert>}
        </Card>
        <Card className="gap-2">
          <CardTitle className="text-base">Columns</CardTitle>
          <dl className="space-y-1.5 text-sm">
            {COLUMNS.map(([c, d]) => (
              <div key={c}>
                <dt className="font-mono text-xs font-semibold">{c}</dt>
                <dd className="text-muted-foreground">{d}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>

      {preview && (
        <Card className="gap-4">
          <CardHeader>
            <CardTitle>2. Review</CardTitle>
            <CardDescription>
              {preview.summary.total} row{preview.summary.total === 1 ? "" : "s"}: {preview.summary.ready} ready, {preview.summary.errors} with problems. Rows with problems are skipped.
            </CardDescription>
          </CardHeader>
          {preview.header_errors.map((e) => (
            <FormAlert key={e}>{e}</FormAlert>
          ))}
          {preview.rows.length > 0 && (
            <div className="max-h-[28rem] overflow-y-auto rounded-xl border">
              <Table head={["Line", "Status", "Name", "Role", "Email / username", "ID", "Class", "Problems"]}>
                {preview.rows.map((r) => (
                  <tr key={r.line} className={r.status === "error" ? "bg-orange-50/50 align-top" : "align-top"}>
                    <td className="px-4 py-2 text-muted-foreground">{r.line}</td>
                    <td className="px-4 py-2">{r.status === "ready" ? <Badge variant="success">Ready</Badge> : <Badge variant="danger">Error</Badge>}</td>
                    <td className="px-4 py-2 font-medium">{r.full_name ?? "—"}</td>
                    <td className="px-4 py-2 capitalize">{r.role ?? "—"}</td>
                    <td className="px-4 py-2">
                      {r.email ?? "—"}
                      {r.username && <span className="block text-xs text-muted-foreground">{r.username}</span>}
                    </td>
                    <td className="px-4 py-2">{r.id_number ?? "—"}</td>
                    <td className="px-4 py-2">{r.class ?? "—"}</td>
                    <td className="px-4 py-2 text-orange-800">{r.errors.join(" ")}</td>
                  </tr>
                ))}
              </Table>
            </div>
          )}
          {preview.header_errors.length === 0 && (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={sendInvites} onCheckedChange={(c) => setSendInvites(c === true)} />
                <Label className="font-medium">Send each new user a set-password link</Label>
              </label>
              <Button onClick={confirm} disabled={busy || preview.summary.ready === 0}>
                {busy ? <Spinner /> : <FileUp />} Create {preview.summary.ready} account{preview.summary.ready === 1 ? "" : "s"}
              </Button>
            </div>
          )}
        </Card>
      )}

      {result && (
        <Card className="gap-4">
          <CardHeader>
            <CardTitle>3. Result</CardTitle>
            <CardDescription>
              {result.summary.created} created, {result.summary.failed} not imported.
            </CardDescription>
          </CardHeader>
          {result.created.length > 0 && (
            <ul className="divide-y rounded-xl border text-sm">
              {result.created.map((c) => (
                <li key={c.id} className="flex items-center gap-2 px-3 py-2">
                  <CheckCircle2 className="size-4 shrink-0 text-emerald-600" />
                  <Link to={`/admin/users/${c.id}`} className="font-semibold text-primary hover:underline">
                    {c.full_name}
                  </Link>
                  <span className="text-muted-foreground">
                    {c.email} · line {c.line}
                    {c.invitation_delivered === false && " · link could not be emailed"}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {result.failed.length > 0 && (
            <ul className="divide-y rounded-xl border text-sm">
              {result.failed.map((f) => (
                <li key={f.line} className="flex items-start gap-2 px-3 py-2">
                  <XCircle className="mt-0.5 size-4 shrink-0 text-orange-600" />
                  <span>
                    <span className="font-semibold">Line {f.line}</span> {f.email && <span className="text-muted-foreground">({f.email})</span>}: {f.errors.join(" ")}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}
