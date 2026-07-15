"use client"

import type { Column } from "@tanstack/react-table"
import { CheckIcon, ListFilterIcon } from "lucide-react"
import { Badge } from "@/vendor/gui/ui/badge"
import { Button } from "@/vendor/gui/ui/button"
import { Checkbox } from "@/vendor/gui/ui/checkbox"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/vendor/gui/ui/command"
import { Popover, PopoverContent, PopoverTrigger } from "@/vendor/gui/ui/popover"
import { Separator } from "@/vendor/gui/ui/separator"
import {
  formatFilterDisplayValue,
  normalizeFilterValue,
} from "@/vendor/gui/lib/data-table/format-filter-value"
import { OverflowText } from "@/vendor/gui/layout/overflow-text"
import { cn } from "@/vendor/gui/utils"

type DataTableFacetedFilterProps<TData, TValue> = {
  column: Column<TData, TValue>
  title?: string
}

export function DataTableFacetedFilter<TData, TValue>({
  column,
  title,
}: DataTableFacetedFilterProps<TData, TValue>) {
  const timeZone =
    Intl.DateTimeFormat().resolvedOptions().timeZone ?? "Europe/Moscow"
  const meta = column.columnDef.meta
  const facets = column.getFacetedUniqueValues()
  const selectedValues = new Set((column.getFilterValue() as string[]) ?? [])

  const options = Array.from(facets.entries())
    .reduce(
      (acc, [value, count]) => {
        const raw = normalizeFilterValue(value, meta, timeZone)
        const label = formatFilterDisplayValue(value, meta, timeZone)
        const existing = acc.get(raw)
        if (existing) {
          existing.count += count ?? 0
        } else {
          acc.set(raw, { label, count: count ?? 0 })
        }
        return acc
      },
      new Map<string, { label: string; count: number }>()
    )
  const sortedOptions = Array.from(options.entries())
    .map(([value, { label, count }]) => ({ value, label, count }))
    .sort((a, b) => a.label.localeCompare(b.label, "ru"))

  const filterTitle = title ?? meta?.title ?? column.id

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative size-7 shrink-0 max-sm:size-6">
          <ListFilterIcon className="size-3.5" />
          {selectedValues.size > 0 && (
            <Badge
              variant="secondary"
              className="pointer-events-none absolute -top-1 -right-1 size-4 rounded-full p-0 text-[10px]"
            >
              {selectedValues.size}
            </Badge>
          )}
          <span className="sr-only">Фильтр {filterTitle}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0 sm:w-96" align="start">
        <Command>
          <CommandInput placeholder={filterTitle} />
          <CommandList>
            <CommandEmpty>Нет значений</CommandEmpty>
            <CommandGroup>
              {sortedOptions.map((option) => {
                const isSelected = selectedValues.has(option.value)
                return (
                  <CommandItem
                    key={option.value}
                    onSelect={() => {
                      const next = new Set(selectedValues)
                      if (isSelected) next.delete(option.value)
                      else next.add(option.value)
                      column.setFilterValue(next.size ? Array.from(next) : undefined)
                    }}
                  >
                    <Checkbox checked={isSelected} className="pointer-events-none" />
                    <OverflowText className="min-w-0 flex-1">
                      {option.label}
                    </OverflowText>
                    <span className="text-muted-foreground tabular-nums">{option.count}</span>
                    <CheckIcon
                      className={cn("size-4", isSelected ? "opacity-100" : "opacity-0")}
                    />
                  </CommandItem>
                )
              })}
            </CommandGroup>
          </CommandList>
          {sortedOptions.length > 0 && (
            <>
              <Separator />
              <div className="flex items-center gap-2 p-2">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 flex-1"
                  onClick={() =>
                    column.setFilterValue(sortedOptions.map((option) => option.value))
                  }
                >
                  Выбрать все
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 flex-1"
                  onClick={() => column.setFilterValue(undefined)}
                >
                  Сбросить
                </Button>
              </div>
            </>
          )}
        </Command>
      </PopoverContent>
    </Popover>
  )
}
