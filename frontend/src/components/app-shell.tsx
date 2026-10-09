import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { BookOpenCheck, Building2, ClipboardList, GraduationCap, Home, LayoutDashboard, LogOut, MessagesSquare, School, ScrollText, Target, Users } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import type { Role } from "@/types";

const NAV: Record<Role, { to: string; label: string; icon: typeof Home; end?: boolean }[]> = {
  student: [
    { to: "/", label: "Home", icon: Home, end: true },
    { to: "/practice", label: "Practice", icon: Target },
    { to: "/community", label: "Community", icon: MessagesSquare },
  ],
  teacher: [
    { to: "/teacher", label: "Dashboard", icon: Users, end: true },
    { to: "/teacher/exams", label: "Exams", icon: ClipboardList },
    { to: "/teacher/community", label: "Teachers", icon: MessagesSquare },
    { to: "/teacher/student-community", label: "Students", icon: BookOpenCheck },
  ],
  admin: [
    { to: "/admin", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/admin/users", label: "Users", icon: Users },
    { to: "/admin/classes", label: "Classes", icon: School },
    { to: "/admin/teacher-assignments", label: "Teaching", icon: BookOpenCheck },
    { to: "/admin/school", label: "School", icon: Building2 },
    { to: "/admin/audit-log", label: "Audit log", icon: ScrollText },
  ],
};

const ROLE_LABEL: Record<Role, string> = { admin: "Administrator", teacher: "Teacher", student: "Student" };

function initials(name: string) {
  return name
    .replace(/^(Cikgu|Ms\.|Mr\.|Puan|Encik)\s+/i, "")
    .split(" ")
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();
}

export function AppShell() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  if (!user) return null;
  const nav = NAV[user.role];

  const logout = async () => {
    await signOut();
    navigate("/login");
  };

  return (
    <div className="min-h-dvh lg:pl-64">
      <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col border-r bg-card/80 p-4 backdrop-blur lg:flex">
        <Brand school={user.school} logoUrl={user.school_logo_url} />
        <nav className="mt-8 flex flex-1 flex-col gap-1" aria-label="Main">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
                  isActive && "bg-gradient-to-r from-violet-600 to-indigo-500 text-white shadow-md shadow-violet-500/25 hover:bg-none hover:text-white",
                )
              }
            >
              <item.icon className="size-5" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-3 rounded-2xl bg-muted/60 p-3">
          <Link to="/profile" className="flex min-w-0 flex-1 items-center gap-3 rounded-xl hover:opacity-80" aria-label="Profile and settings">
            <Avatar name={user.full_name} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-bold">{user.full_name}</p>
              <p className="truncate text-xs text-muted-foreground">{user.class_name ?? ROLE_LABEL[user.role]}</p>
            </div>
          </Link>
          <button onClick={logout} className="rounded-lg p-2 text-muted-foreground hover:bg-card hover:text-foreground" aria-label="Sign out">
            <LogOut className="size-4" />
          </button>
        </div>
      </aside>

      <header className="sticky top-0 z-30 flex items-center justify-between border-b bg-card/80 px-4 py-3 backdrop-blur lg:hidden">
        <Brand school={user.school} logoUrl={user.school_logo_url} />
        <div className="flex items-center gap-1">
          <Link to="/profile" aria-label="Profile and settings">
            <Avatar name={user.full_name} small />
          </Link>
          <button onClick={logout} className="rounded-lg p-2 text-muted-foreground hover:bg-muted" aria-label="Sign out">
            <LogOut className="size-5" />
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 pt-6 pb-28 sm:px-6 lg:px-8 lg:pb-10">
        <Outlet />
      </main>

      <nav className="fixed inset-x-0 bottom-0 z-30 flex justify-around border-t bg-card/95 px-2 pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] backdrop-blur lg:hidden" aria-label="Main">
        {nav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              cn("flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-xl px-1 py-1.5 text-[11px] font-semibold text-muted-foreground", isActive && "text-primary")
            }
          >
            {({ isActive }) => (
              <>
                <span className={cn("rounded-full px-3 py-1 transition-colors", isActive && "bg-primary/10")}>
                  <item.icon className="size-5" />
                </span>
                {item.label}
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

function Avatar({ name, small }: { name: string; small?: boolean }) {
  return (
    <div className={cn("flex shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-amber-300 to-pink-400 font-bold text-white", small ? "size-8 text-xs" : "size-10 text-sm")}>
      {initials(name)}
    </div>
  );
}

export function Brand({ school, logoUrl }: { school?: string | null; logoUrl?: string | null }) {
  return (
    <div className="flex items-center gap-2.5">
      {logoUrl ? (
        <img src={logoUrl} alt="" className="size-9 shrink-0 rounded-xl border bg-card object-contain" />
      ) : (
        <div className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-blue-500 text-white shadow-md shadow-violet-500/30">
          <GraduationCap className="size-5" />
        </div>
      )}
      <div className="min-w-0 leading-tight">
        <p className="text-sm font-extrabold tracking-tight">MINDA</p>
        <p className="truncate text-[11px] font-medium text-muted-foreground">{school ?? "Learn. Practice. Master."}</p>
      </div>
    </div>
  );
}
