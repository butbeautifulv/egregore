package tableutil

import (
	"github.com/charmbracelet/bubbles/table"

	"github.com/butbeautifulv/egregore/tui/internal/textutil"
)

const minColWidth = 4

// ColumnSpec describes a table column for responsive layout.
type ColumnSpec struct {
	Title    string
	MinWidth int
	Weight   int // 0 = fixed share; >0 shares remaining width
}

// Layout computes column widths so their sum fits totalWidth.
func Layout(totalWidth int, specs []ColumnSpec) []table.Column {
	n := len(specs)
	if n == 0 {
		return nil
	}
	if totalWidth < n*minColWidth {
		totalWidth = n * minColWidth
	}

	widths := make([]int, n)
	fixed := 0
	flexWeight := 0
	for i, s := range specs {
		if s.Weight <= 0 {
			w := s.MinWidth
			if w < minColWidth {
				w = minColWidth
			}
			widths[i] = w
			fixed += w
		} else {
			flexWeight += s.Weight
		}
	}

	remaining := totalWidth - fixed
	if remaining < 0 {
		remaining = 0
	}

	for i, s := range specs {
		if s.Weight <= 0 {
			continue
		}
		w := minColWidth
		if flexWeight > 0 {
			w = remaining * s.Weight / flexWeight
		}
		if s.MinWidth > w {
			w = s.MinWidth
		}
		if w < minColWidth {
			w = minColWidth
		}
		widths[i] = w
	}

	widths = fitWidths(widths, totalWidth, minColWidth)

	cols := make([]table.Column, n)
	for i, s := range specs {
		cols[i] = table.Column{
			Title: textutil.Truncate(s.Title, widths[i]),
			Width: widths[i],
		}
	}
	return cols
}

func fitWidths(widths []int, target, floor int) []int {
	if len(widths) == 0 {
		return widths
	}
	out := append([]int(nil), widths...)
	if sum(out) <= target {
		for sum(out) < target {
			out[0]++
		}
		return out
	}
	for sum(out) > target {
		idx := -1
		maxW := floor - 1
		for i, w := range out {
			if w > maxW {
				maxW = w
				idx = i
			}
		}
		if idx < 0 {
			each := target / len(out)
			if each < 1 {
				each = 1
			}
			for i := range out {
				out[i] = each
			}
			break
		}
		out[idx]--
	}
	return out
}

func sum(widths []int) int {
	total := 0
	for _, w := range widths {
		total += w
	}
	return total
}

// Widths returns display widths from table columns.
func Widths(cols []table.Column) []int {
	out := make([]int, len(cols))
	for i, c := range cols {
		out[i] = c.Width
	}
	return out
}

// ApplyLayout sets columns, width, and height on a bubbles table.
func ApplyLayout(t *table.Model, width, height int, specs []ColumnSpec) {
	if width <= 0 {
		width = 80
	}
	cols := Layout(width, specs)
	t.SetColumns(cols)
	t.SetWidth(width)
	if height > 0 {
		t.SetHeight(height)
	}
}
