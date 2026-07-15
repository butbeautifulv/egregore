"use client"

import { ThemeProvider as GuiThemeProvider } from "@/vendor/gui/theme/theme-provider"
import { TooltipProvider } from "@/vendor/gui/ui/tooltip"

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <GuiThemeProvider>
      <TooltipProvider>{children}</TooltipProvider>
    </GuiThemeProvider>
  )
}
