import * as React from "react";
import * as ProgressPrimitive from "@radix-ui/react-progress";
import { cn } from "@/lib/utils";

function Progress({
  className,
  value,
  indicatorClassName,
  ...props
}: React.ComponentProps<typeof ProgressPrimitive.Root> & { indicatorClassName?: string }) {
  return (
    <ProgressPrimitive.Root data-slot="progress" className={cn("bg-muted relative h-2.5 w-full overflow-hidden rounded-full", className)} value={value} {...props}>
      <ProgressPrimitive.Indicator
        data-slot="progress-indicator"
        className={cn("h-full w-full flex-1 rounded-full bg-gradient-to-r from-violet-500 to-indigo-500 transition-transform duration-700 ease-out", indicatorClassName)}
        style={{ transform: `translateX(-${100 - Math.min(100, Math.max(0, value || 0))}%)` }}
      />
    </ProgressPrimitive.Root>
  );
}

export { Progress };
