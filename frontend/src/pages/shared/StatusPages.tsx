import { Link } from "react-router-dom";
import { Compass, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { roleHome, useAuth } from "@/lib/auth";

function StatusPage({ icon: Icon, title, message }: { icon: typeof Compass; title: string; message: string }) {
  const { user } = useAuth();
  return (
    <div className="flex min-h-[60dvh] flex-col items-center justify-center gap-4 p-6 text-center">
      <div className="flex size-16 items-center justify-center rounded-2xl bg-muted">
        <Icon className="size-8 text-muted-foreground" />
      </div>
      <div className="space-y-1">
        <h1 className="text-2xl font-extrabold tracking-tight">{title}</h1>
        <p className="mx-auto max-w-sm text-muted-foreground">{message}</p>
      </div>
      <Button asChild variant="gradient">
        <Link to={user ? roleHome(user.role) : "/login"}>{user ? "Go to my dashboard" : "Sign in"}</Link>
      </Button>
    </div>
  );
}

export function NotFoundPage() {
  return <StatusPage icon={Compass} title="Page not found" message="The page you're looking for doesn't exist or has moved." />;
}

export function AccessDeniedPage() {
  return <StatusPage icon={ShieldAlert} title="Access denied" message="Your account doesn't have permission to view this page. If you think this is a mistake, contact your school administrator." />;
}
