import { Geist_Mono, Inter } from "next/font/google"

import "./globals.css"
import { AppShellLayout } from "@/components/app-shell-layout"
import { ThemeProvider } from "@/components/theme-provider"
import { Toaster } from "@/vendor/gui/ui/sonner"
import { cn } from "@/vendor/gui/utils"

const inter = Inter({subsets:['latin'],variable:'--font-sans'})

const fontMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
})

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="en"
      data-gui-style="lyra"
      suppressHydrationWarning
      className={cn("antialiased", fontMono.variable, "font-sans", inter.variable)}
    >
      <body>
        <ThemeProvider>
          <AppShellLayout>{children}</AppShellLayout>
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  )
}
