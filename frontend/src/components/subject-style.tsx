import {
  Atom,
  BookOpen,
  Calculator,
  FlaskConical,
  Globe,
  HeartHandshake,
  Landmark,
  Languages,
  Leaf,
  Sigma,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

const ICONS: Record<string, LucideIcon> = {
  calculator: Calculator,
  sigma: Sigma,
  atom: Atom,
  "flask-conical": FlaskConical,
  leaf: Leaf,
  landmark: Landmark,
  globe: Globe,
  languages: Languages,
  "book-open": BookOpen,
  "heart-handshake": HeartHandshake,
};

// Full class strings so Tailwind can detect them at build time.
const COLORS: Record<string, { gradient: string; soft: string; ring: string }> = {
  violet: { gradient: "from-violet-500 to-purple-600", soft: "bg-violet-100 text-violet-700", ring: "#8b5cf6" },
  indigo: { gradient: "from-indigo-500 to-blue-600", soft: "bg-indigo-100 text-indigo-700", ring: "#6366f1" },
  cyan: { gradient: "from-cyan-500 to-sky-600", soft: "bg-cyan-100 text-cyan-700", ring: "#06b6d4" },
  emerald: { gradient: "from-emerald-500 to-teal-600", soft: "bg-emerald-100 text-emerald-700", ring: "#10b981" },
  lime: { gradient: "from-lime-500 to-green-600", soft: "bg-lime-100 text-lime-700", ring: "#84cc16" },
  amber: { gradient: "from-amber-400 to-orange-500", soft: "bg-amber-100 text-amber-700", ring: "#f59e0b" },
  teal: { gradient: "from-teal-500 to-cyan-600", soft: "bg-teal-100 text-teal-700", ring: "#14b8a6" },
  rose: { gradient: "from-rose-500 to-pink-600", soft: "bg-rose-100 text-rose-700", ring: "#f43f5e" },
  sky: { gradient: "from-sky-500 to-blue-600", soft: "bg-sky-100 text-sky-700", ring: "#0ea5e9" },
  pink: { gradient: "from-pink-500 to-fuchsia-600", soft: "bg-pink-100 text-pink-700", ring: "#ec4899" },
};

export function subjectColor(color: string) {
  return COLORS[color] ?? COLORS.violet;
}

export function SubjectIcon({ icon, color, className, size = "md" }: { icon: string; color: string; className?: string; size?: "sm" | "md" | "lg" }) {
  const Icon = ICONS[icon] ?? BookOpen;
  const dims = { sm: "size-8 rounded-lg [&_svg]:size-4", md: "size-11 rounded-xl [&_svg]:size-5", lg: "size-14 rounded-2xl [&_svg]:size-7" }[size];
  return (
    <div className={cn("flex shrink-0 items-center justify-center bg-gradient-to-br text-white shadow-sm", subjectColor(color).gradient, dims, className)}>
      <Icon />
    </div>
  );
}
