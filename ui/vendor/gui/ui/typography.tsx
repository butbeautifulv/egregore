import type { ReactNode } from "react"

/** Full-width hairline that fades out toward the end (e.g. near header badges). */
export const pageHeaderHairlineClassName =
  "relative after:pointer-events-none after:absolute after:inset-x-0 after:bottom-0 after:h-px after:bg-gradient-to-r after:from-border after:via-border/50 after:to-transparent"

export function TypographyH1({ children }: { children: ReactNode }) {
  return (
    <h1 className="scroll-m-20 text-2xl font-bold tracking-tight text-balance sm:text-3xl">
      {children}
    </h1>
  )
}

export function TypographyH2({ children }: { children: ReactNode }) {
  return (
    <h2 className="scroll-m-20 text-2xl font-bold tracking-tight">
      {children}
    </h2>
  )
}

export function TypographyH3({ children }: { children: ReactNode }) {
  return (
    <h3 className="scroll-m-20 text-lg font-semibold tracking-tight">{children}</h3>
  )
}

export function TypographyLead({ children }: { children: ReactNode }) {
  return <p className="text-muted-foreground text-sm">{children}</p>
}

export function TypographyMuted({ children }: { children: ReactNode }) {
  return <p className="text-muted-foreground text-sm">{children}</p>
}

export function TypographyInlineCode({ children }: { children: ReactNode }) {
  return (
    <code className="relative rounded bg-muted px-[0.3rem] py-[0.2rem] font-mono text-sm font-semibold">
      {children}
    </code>
  )
}
