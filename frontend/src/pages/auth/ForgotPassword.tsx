import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link } from "react-router-dom";
import { ArrowLeft, Mail } from "lucide-react";
import { AuthLayout } from "@/components/auth-layout";
import { Field, FormAlert } from "@/components/form";
import { Spinner } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { supabase } from "@/lib/auth";

const schema = z.object({ identifier: z.string().trim().min(1, "Enter your email or username.") });
type Values = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState } = useForm<Values>({ resolver: zodResolver(schema) });

  const submit = async ({ identifier }: Values) => {
    setError(null);
    try {
      if (supabase) {
        const { error: e } = await supabase.auth.resetPasswordForEmail(identifier, { redirectTo: `${window.location.origin}/reset-password` });
        if (e) throw new Error(e.message);
        setSent("If an active account matches, a password reset link has been sent.");
      } else {
        setSent((await api.post<{ message: string }>("/api/auth/forgot-password", { identifier })).message);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send the reset link");
    }
  };

  return (
    <AuthLayout title="Forgot your password?" subtitle="We'll send a reset link to the email on your school account.">
      {sent ? (
        <div className="space-y-4">
          <FormAlert tone="success">{sent}</FormAlert>
          <p className="text-sm text-muted-foreground">
            The link works once and expires after 30 minutes. If nothing arrives, ask your school administrator to reset your password.
          </p>
        </div>
      ) : (
        <form onSubmit={handleSubmit(submit)} className="space-y-4" noValidate>
          <Field id="identifier" label={supabase ? "Email" : "Email or username"} error={formState.errors.identifier?.message}>
            <Input id="identifier" autoComplete="username" aria-invalid={!!formState.errors.identifier} {...register("identifier")} />
          </Field>
          {error && <FormAlert>{error}</FormAlert>}
          <Button type="submit" variant="gradient" size="lg" className="w-full" disabled={formState.isSubmitting}>
            {formState.isSubmitting ? <Spinner /> : <Mail />} Send reset link
          </Button>
        </form>
      )}
      <Link to="/login" className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:underline">
        <ArrowLeft className="size-4" /> Back to sign in
      </Link>
    </AuthLayout>
  );
}
