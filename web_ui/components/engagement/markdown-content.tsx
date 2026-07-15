"use client"

import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

import { cn } from "@/lib/utils"

export function MarkdownContent({
  children,
  className,
}: {
  children: string
  className?: string
}) {
  return (
    <div className={cn("text-sm leading-relaxed", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
        h1: ({ children: c }) => <h1 className="mt-4 mb-2 text-lg font-semibold first:mt-0">{c}</h1>,
        h2: ({ children: c }) => <h2 className="mt-4 mb-2 text-base font-semibold first:mt-0">{c}</h2>,
        h3: ({ children: c }) => <h3 className="mt-3 mb-1 text-sm font-semibold first:mt-0">{c}</h3>,
        p: ({ children: c }) => <p className="mb-2 last:mb-0">{c}</p>,
        ul: ({ children: c }) => <ul className="mb-2 list-disc pl-5 last:mb-0">{c}</ul>,
        ol: ({ children: c }) => <ol className="mb-2 list-decimal pl-5 last:mb-0">{c}</ol>,
        li: ({ children: c }) => <li className="mb-1">{c}</li>,
        blockquote: ({ children: c }) => (
          <blockquote className="border-muted-foreground/40 text-muted-foreground my-2 border-l-2 pl-3 italic">
            {c}
          </blockquote>
        ),
        code: ({ className: codeClass, children: c }) =>
          codeClass ? (
            <code className="bg-muted block overflow-x-auto rounded p-2 text-xs">{c}</code>
          ) : (
            <code className="bg-muted rounded px-1 py-0.5 text-xs">{c}</code>
          ),
        pre: ({ children: c }) => <pre className="mb-2 overflow-x-auto last:mb-0">{c}</pre>,
        table: ({ children: c }) => (
          <div className="my-2 overflow-x-auto">
            <table className="w-full border-collapse text-xs">{c}</table>
          </div>
        ),
        thead: ({ children: c }) => <thead className="bg-muted/60">{c}</thead>,
        th: ({ children: c }) => <th className="border px-2 py-1 text-left font-medium">{c}</th>,
        td: ({ children: c }) => <td className="border px-2 py-1 align-top">{c}</td>,
        hr: () => <hr className="border-muted my-3" />,
        strong: ({ children: c }) => <strong className="font-semibold">{c}</strong>,
      }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}
