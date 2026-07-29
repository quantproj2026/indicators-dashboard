"use client";

import { Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/**
 * The `dark` class on `<html>` is the source of truth -- an inline script in the
 * root layout sets it before first paint, so there is no flash. Subscribing to
 * it rather than mirroring it into state means the icon can never drift out of
 * sync with the document, and `useSyncExternalStore` handles the
 * server/client difference during hydration without a mismatch.
 */
function subscribe(onChange: () => void): () => void {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });
  return () => observer.disconnect();
}

function readTheme(): boolean {
  return document.documentElement.classList.contains("dark");
}

export function ThemeToggle() {
  // Dark is the product default, so that is the server-rendered assumption.
  const isDark = useSyncExternalStore(subscribe, readTheme, () => true);

  function toggle() {
    const next = !isDark;
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {
      // Private browsing: the toggle still works for this session.
    }
  }

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={toggle}
            aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
          >
            {isDark ? (
              <Moon aria-hidden className="size-4" />
            ) : (
              <Sun aria-hidden className="size-4" />
            )}
          </Button>
        }
      />
      <TooltipContent>{isDark ? "Light theme" : "Dark theme"}</TooltipContent>
    </Tooltip>
  );
}
