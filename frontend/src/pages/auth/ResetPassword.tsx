import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowLeft, KeyRound } from "lucide-react";
import { AuthLayout } from "@/components/auth-layout";
import { Field, FormAlert } from "@/components/form";
import { Spinner } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { supabase } from "@/lib/auth";
import { confirmMessage, confirmPasswords, newPassword } from "@/lib/validation";

const schema = z.object({ new_password: newPassword, confirm: z.string() }).refine(confirmPasswords, confirmMessage);
type Values = z.infer<typeof schema>;

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState } = useForm<Values>({ resolver: zodResolver(schema) });
  const missingLink = !supabase && !token;

  const submit = async ({ new_password }: Values) => {
    setError(null);
    try {
      if (supabase) {
        const { error: e } = await supabase.auth.updateUser({ password: new_password });
        if (e) throw new Error(e.message);
        await supabase.auth.signOut();
        setDone("Your password has been reset. You can now sign in.");
      } else {
        setDone((await api.post<{ message: string }>("/api/auth/reset-password", { token, new_password })).message);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reset the password");
    }
  };

  return (
    <AuthLayout title="Choose a new password" subtitle="Use at least 8 characters with a letter and a number.">
      {done ? (
        <div className="space-y-4">
          <FormAlert tone="success">{done}</FormAlert>
          <Button asChild variant="gradient" size="lg" className="w-full">
            <Link to="/login">Sign in</Link>
          </Button>
        </div>
      ) : missingLink ? (
        <FormAlert>This page needs the link from your reset email. Request a new link if it has expired.</FormAlert>
      ) : (
        <form onSubmit={handleSubmit(submit)} className="space-y-4" noValidate>
          <Field id="new_password" label="New password" error={formState.errors.new_password?.message}>
            <Input id="new_password" type="password" autoComplete="new-password" aria-invalid={!!formState.errors.new_password} {...register("new_password")} />
          </Field>
          <Field id="confirm" label="Confirm new password" error={formState.errors.confirm?.message}>
            <Input id="confirm" type="password" autoComplete="new-password" aria-invalid={!!formState.errors.confirm} {...register("confirm")} />
          </Field>
          {error && <FormAlert>{error}</FormAlert>}
          <Button type="submit" variant="gradient" size="lg" className="w-full" disabled={formState.isSubmitting}>
            {formState.isSubmitting ? <Spinner /> : <KeyRound />} Reset password
          </Button>
        </form>
      )}
      <div className="flex justify-between text-sm font-semibold">
        <Link to="/login" className="inline-flex items-center gap-1.5 text-primary hover:underline">
          <ArrowLeft className="size-4" /> Back to sign in
        </Link>
        {!done && (
          <Link to="/forgot-password" className="text-muted-foreground hover:underline">
            Request a new link
          </Link>
        )}
      </div>
    </AuthLayout>
  );
}
