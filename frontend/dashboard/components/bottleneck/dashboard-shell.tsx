"use client";

import { Activity, Bot, Boxes, Gauge, Menu, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

const navigation = [
  { label: "Command center", href: "#overview", icon: Gauge },
  { label: "Incidents", href: "#incidents", icon: Activity },
  { label: "Supplier network", href: "#suppliers", icon: Boxes },
  { label: "Agent workflow", href: "#workflow", icon: Bot },
];

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="min-h-screen bg-muted lg:grid lg:grid-cols-[17rem_minmax(0,1fr)]">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="fixed left-4 top-4 z-50 flex size-10 items-center justify-center rounded-md border border-border bg-background lg:hidden"
        aria-label={open ? "Close navigation" : "Open navigation"}
      >
        {open ? <X className="size-5" /> : <Menu className="size-5" />}
      </button>

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-68 flex-col border-r border-border bg-background p-4 transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="mt-14 rounded-lg bg-primary p-4 text-primary-foreground lg:mt-0">
          <div className="mb-6 flex size-11 items-center justify-center rounded-md bg-white/10">
            <ShieldCheck className="size-6" />
          </div>
          <p className="font-display text-3xl tracking-wide">BOTTLENECK</p>
          <p className="mt-1 text-xs uppercase text-primary-foreground/65">
            Agentic recovery console
          </p>
        </div>

        <nav className="mt-6 space-y-2" aria-label="Dashboard sections">
          {navigation.map((item) => (
            <a
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className="flex items-center gap-3 rounded-md px-3 py-3 text-sm uppercase text-muted-foreground transition hover:bg-accent hover:text-foreground first:bg-accent first:text-foreground"
            >
              <item.icon className="size-4" />
              {item.label}
            </a>
          ))}
        </nav>

        <div className="mt-auto rounded-lg border border-border bg-accent p-4">
          <div className="flex items-center gap-2 text-success">
            <span className="size-2 rounded-full bg-success" />
            <span className="text-xs font-bold uppercase">Local system online</span>
          </div>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            Decisions stay human-controlled. No purchase order is executed automatically.
          </p>
        </div>
      </aside>

      <main className="min-w-0">{children}</main>
    </div>
  );
}
