package presentation

import (
	"strings"
	"time"

	"github.com/butbeautifulv/egregore/tui/internal/api"
	"github.com/butbeautifulv/egregore/tui/internal/style"
	"github.com/butbeautifulv/egregore/tui/internal/ui/tableutil"
)

// WorkOrderColumnSpecs returns responsive column layout for work order tables.
func WorkOrderColumnSpecs() []tableutil.ColumnSpec {
	return WorkOrderColumnSpecsForWidth(80)
}

// WorkOrderColumnSpecsForWidth picks columns that fit the available width.
func WorkOrderColumnSpecsForWidth(totalWidth int) []tableutil.ColumnSpec {
	switch {
	case totalWidth < 34:
		return []tableutil.ColumnSpec{
			{Title: "St", MinWidth: 6, Weight: 0},
			{Title: "Goal", MinWidth: 8, Weight: 1},
		}
	case totalWidth < 52:
		return []tableutil.ColumnSpec{
			{Title: "Status", MinWidth: 8, Weight: 0},
			{Title: "Goal", MinWidth: 8, Weight: 2},
			{Title: "When", MinWidth: 11, Weight: 0},
		}
	default:
		return []tableutil.ColumnSpec{
			{Title: "Status", MinWidth: 8, Weight: 0},
			{Title: "Goal", MinWidth: 8, Weight: 3},
			{Title: "Updated", MinWidth: 11, Weight: 0},
			{Title: "Personas", MinWidth: 6, Weight: 1},
		}
	}
}

// HeadersFromSpecs returns table headers for the given column specs.
func HeadersFromSpecs(specs []tableutil.ColumnSpec) []string {
	out := make([]string, len(specs))
	for i, spec := range specs {
		out[i] = spec.Title
	}
	return out
}

// WorkOrderCells returns display cells for a work order row.
func WorkOrderCells(wo api.InvestigationSummary) []string {
	return WorkOrderCellsSized(wo, WorkOrderColumnSpecs(), nil)
}

// WorkOrderCellsSized returns cells truncated to optional column widths.
func WorkOrderCellsSized(wo api.InvestigationSummary, specs []tableutil.ColumnSpec, colWidths []int) []string {
	if len(specs) == 0 {
		specs = WorkOrderColumnSpecs()
	}
	cells := make([]string, len(specs))
	for i, spec := range specs {
		cell := workOrderField(wo, spec.Title)
		if i < len(colWidths) && colWidths[i] > 0 {
			cell = style.Truncate(cell, colWidths[i])
		}
		cells[i] = cell
	}
	return cells
}

func workOrderField(wo api.InvestigationSummary, title string) string {
	switch title {
	case "St", "Status":
		return style.StatusStyle(wo.Status).Render(padStatus(wo.Status))
	case "Goal":
		goal := strings.TrimSpace(wo.Goal)
		if goal == "" {
			goal = wo.InvestigationID
		}
		return goal
	case "When", "Updated":
		return formatUpdated(wo.UpdatedAt)
	case "Personas":
		return strings.Join(wo.CompletedPersonas, ",")
	default:
		return ""
	}
}

// WorkOrderListLine returns a single-line summary for the left-panel list.
func WorkOrderListLine(wo api.InvestigationSummary, width int) string {
	goal := strings.TrimSpace(wo.Goal)
	if goal == "" {
		goal = wo.InvestigationID
	}
	status := style.StatusStyle(wo.Status).Render(padStatus(wo.Status))
	return FormatPair(status, goal, width)
}

func padStatus(s string) string {
	if len(s) > 8 {
		return s[:8]
	}
	return s
}

func formatUpdated(raw string) string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return ""
	}
	if t, err := time.Parse(time.RFC3339, raw); err == nil {
		return t.Local().Format("01-02 15:04")
	}
	if len(raw) > 11 {
		return raw[:11]
	}
	return raw
}

// WorkOrderHeader returns column titles.
func WorkOrderHeader() []string {
	return []string{"Status", "Goal", "Updated", "Personas"}
}
