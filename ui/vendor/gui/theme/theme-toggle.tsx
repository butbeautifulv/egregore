"use client"

import * as React from "react"
import { MoonIcon, SunIcon } from "lucide-react"
import { useTheme } from "@/vendor/gui/theme/theme-provider"

import { Button } from "@/vendor/gui/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/vendor/gui/ui/tooltip"

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const mounted = React.useSyncExternalStore(
    () => () => {},
    () => true,
    () => false
  )

  if (!mounted) {
    return (
      <Button
        variant="ghost"
        size="icon"
        disabled
        aria-label="Переключить тему"
      >
        <MoonIcon />
      </Button>
    )
  }

  const isDark = resolvedTheme === "dark"
  const label = isDark ? "Светлая тема" : "Тёмная тема"

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label={label}
          onClick={() => setTheme(isDark ? "light" : "dark")}
        >
          {isDark ? <SunIcon /> : <MoonIcon />}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}
