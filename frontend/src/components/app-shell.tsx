import { useEffect, useState } from "react";
import { Link, matchPath, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Bell, BookOpen, BookOpenCheck, Building2, CalendarDays, ClipboardList, GraduationCap, Home, LayoutDashboard, LogOut, Megaphone, Menu, MessagesSquare, School, ScrollText, ShieldAlert, Target, Users } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import type { Role } from "@/types";

type NavItem = { to: string; label: string; icon: typeof Home; end?: boolean };

const NAV: Record<Role, NavItem[]> = {
  student: [
    { to: "/", label: "Home", icon: Home, end: true },
    { to: "/practice", label: "Practice", icon: Target },
    { to: "/exams", label: "Exams", icon: ClipboardList },
    { to: "/community", label: "Community", icon: MessagesSquare },
    { to: "/memos", label: "Memos", icon: Megaphone },
    { to: "/calendar", label: "Calendar", icon: CalendarDays },
  ],
  teacher: [
    { to: "/teacher", label: "Dashboard", icon: Users, end: true },
    { to: "/teacher/exams", label: "Exams", icon: ClipboardList },
    { to: "/teacher/community", label: "Teachers", icon: MessagesSquare },
    { to: "/teacher/student-community", label: "Students", icon: BookOpenCheck },
    { to: "/memos", label: "Memos", icon: Megaphone },
    { to: "/calendar", label: "Calendar", icon: CalendarDays },
  ],
  admin: [
    { to: "/admin", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/admin/users", label: "Users", icon: Users },
    { to: "/admin/classes", label: "Classes", icon: School },
    { to: "/admin/teacher-assignments", label: "Teaching", icon: BookOpenCheck },
    { to: "/admin/content", label: "Content", icon: BookOpen },
    { to: "/admin/memos", label: "Memos", icon: Megaphone },
    { to: "/admin/moderation", label: "Moderation", icon: ShieldAlert },
    { to: "/calendar", label: "Calendar", icon: CalendarDays },
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
        <NotificationBell withLabel />
        <div className="mt-2 flex items-center gap-3 rounded-2xl bg-muted/60 p-3">
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
          <NotificationBell />
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

      <MobileNav nav={nav} />
    </div>
  );
}

const MOBILE_SLOTS = 4;

function MobileNav({ nav }: { nav: NavItem[] }) {
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const primary = nav.length > MOBILE_SLOTS + 1 ? nav.slice(0, MOBILE_SLOTS) : nav;
  const overflow = nav.slice(primary.length);
  const overflowActive = overflow.some((item) => matchPath({ path: item.to, end: !!item.end }, location.pathname));

  useEffect(() => setOpen(false), [location.pathname]);

  const tab = "flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-xl px-1 py-1.5 text-[11px] font-semibold text-muted-foreground";
  const pill = (active: boolean) => cn("rounded-full px-3 py-1 transition-colors", active && "bg-primary/10");

  return (
    <>
      {open && (
        <>
          <button className="fixed inset-0 z-30 bg-black/20 lg:hidden" aria-label="Close menu" onClick={() => setOpen(false)} />
          <div id="more-nav" className="fixed inset-x-3 bottom-[calc(5.25rem+env(safe-area-inset-bottom))] z-40 grid grid-cols-3 gap-1 rounded-2xl border bg-card p-2 shadow-xl lg:hidden">
            {overflow.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => cn("flex flex-col items-center gap-1 rounded-xl px-2 py-3 text-xs font-semibold text-muted-foreground hover:bg-muted", isActive && "bg-primary/10 text-primary")}
              >
                <item.icon className="size-5" />
                {item.label}
              </NavLink>
            ))}
          </div>
        </>
      )}
      <nav className="fixed inset-x-0 bottom-0 z-40 flex justify-around border-t bg-card/95 px-2 pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] backdrop-blur lg:hidden" aria-label="Main">
        {primary.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => cn(tab, isActive && "text-primary")}>
            {({ isActive }) => (
              <>
                <span className={pill(isActive)}>
                  <item.icon className="size-5" />
                </span>
                <span className="max-w-full truncate">{item.label}</span>
              </>
            )}
          </NavLink>
        ))}
        {overflow.length > 0 && (
          <button type="button" className={cn(tab, (open || overflowActive) && "text-primary")} aria-expanded={open} aria-controls="more-nav" onClick={() => setOpen((v) => !v)}>
            <span className={pill(open || overflowActive)}>
              <Menu className="size-5" />
            </span>
            More
          </button>
        )}
      </nav>
    </>
  );
}

function NotificationBell({ withLabel }: { withLabel?: boolean }) {
  const location = useLocation();
  const [count, setCount] = useState(0);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api
        .get<{ count: number }>("/api/notifications/unread-count")
        .then((r) => alive && setCount(r.count))
        .catch(() => undefined);
    load();
    const timer = window.setInterval(load, 60_000);
    window.addEventListener("notifications-changed", load);
    return () => {
      alive = false;
      window.clearInterval(timer);
      window.removeEventListener("notifications-changed", load);
    };
  }, [location.pathname]);

  const label = count ? `Notifications (${count} unread)` : "Notifications";
  return (
    <NavLink
      to="/notifications"
      aria-label={label}
      className={({ isActive }) =>
        cn(
          "relative flex items-center gap-3 rounded-xl text-sm font-semibold text-muted-foreground hover:bg-accent hover:text-foreground",
          withLabel ? "px-3 py-2.5" : "p-2",
          isActive && "text-primary",
        )
      }
    >
      <span className="relative">
        <Bell className="size-5" />
        {count > 0 && (
          <span className="absolute -top-1.5 -right-1.5 min-w-4 rounded-full bg-orange-500 px-1 text-center text-[10px] leading-4 font-bold text-white">{count > 99 ? "99+" : count}</span>
        )}
      </span>
      {withLabel && "Notifications"}
    </NavLink>
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
