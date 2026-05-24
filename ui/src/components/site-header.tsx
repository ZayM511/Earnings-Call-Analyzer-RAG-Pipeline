"use client";

import * as React from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";

/**
 * Sticky shared header used by every route in the app. Carries the brand
 * mark (earnings-call icon) + a two-line title group with the project name
 * on top and the author credit below, the corpus status line, and the nav.
 */
export function SiteHeader() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-30 border-b border-(--border) bg-(--card)/85 backdrop-blur-xl">
      <div className="mx-auto max-w-7xl px-6 py-3 flex flex-wrap items-center gap-4">
        <Link
          href="/"
          className="flex items-center gap-3 shrink-0"
          aria-label="Earnings Call Analyzer home"
        >
          <span
            aria-hidden="true"
            className="relative inline-flex size-8 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-(--accent) ring-1 ring-(--accent)/40 shadow-sm"
          >
            <Image
              src="/earnings-call-icon.png"
              alt=""
              width={32}
              height={32}
              priority
              className="size-8 object-contain select-none mix-blend-screen invert"
            />
          </span>
          <div className="flex flex-col leading-tight">
            <span className="text-base font-semibold tracking-tight text-(--foreground)">
              Earnings Call Analyzer
            </span>
            <span className="text-[11px] italic text-(--muted-foreground)">
              By Isaiah M.
            </span>
          </div>
        </Link>

        <span className="hidden md:inline text-xs text-(--muted-foreground)">
          Mag 7 · 41 calls · 1,097 chunks · Q2 2024 → Q1 2026
        </span>

        <nav className="ml-auto flex items-center gap-1 text-sm">
          <NavLink href="/" current={pathname === "/"}>Ask</NavLink>
          <NavLink href="/compare" current={pathname === "/compare"}>Compare</NavLink>
          <NavLink href="/how-i-made-this" current={pathname === "/how-i-made-this"}>
            How I Made This
          </NavLink>
          <a
            href="https://github.com/ZayM511/Earnings-Call-Analyzer-RAG-Pipeline"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-md px-2 py-1 text-(--muted-foreground) hover:text-(--accent) hover:bg-(--accent)/10 transition-colors"
            data-testid="header-github"
          >
            GitHub
          </a>
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}

function NavLink({
  href,
  current,
  children,
}: {
  href: string;
  current: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "rounded-md px-2 py-1 transition-colors",
        current
          ? "text-(--foreground) font-medium bg-(--accent)/12"
          : "text-(--muted-foreground) hover:text-(--accent) hover:bg-(--accent)/10",
      )}
    >
      {children}
    </Link>
  );
}
