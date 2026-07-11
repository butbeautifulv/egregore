package presentation

import (
	"regexp"
	"strings"

	"github.com/mattn/go-runewidth"

	"github.com/butbeautifulv/egregore/tui/internal/textutil"
)

var ansiRe = regexp.MustCompile(`\x1b\[[0-9;]*m`)

// Decolorise strips ANSI escape sequences for width calculation.
func Decolorise(s string) string {
	return ansiRe.ReplaceAllString(s, "")
}

// PadWidths returns per-column pad widths for a table.
func PadWidths(rows [][]string) []int {
	if len(rows) == 0 {
		return nil
	}
	cols := len(rows[0])
	widths := make([]int, cols)
	for _, row := range rows {
		for i, cell := range row {
			if i >= cols {
				break
			}
			w := runewidth.StringWidth(Decolorise(cell))
			if w > widths[i] {
				widths[i] = w
			}
		}
	}
	return widths
}

// RenderTable renders rows with column padding (ANSI-safe).
func RenderTable(rows [][]string) string {
	if len(rows) == 0 {
		return ""
	}
	pads := PadWidths(rows)
	return renderTableWithPads(rows, pads)
}

// RenderTableSized renders rows using explicit column widths (cells truncated to fit).
func RenderTableSized(rows [][]string, colWidths []int) string {
	if len(rows) == 0 {
		return ""
	}
	pads := make([]int, len(colWidths))
	copy(pads, colWidths)
	return renderTableWithPads(rows, pads)
}

func renderTableWithPads(rows [][]string, pads []int) string {
	lines := make([]string, len(rows))
	for i, row := range rows {
		parts := make([]string, len(row))
		for j, cell := range row {
			target := 0
			if j < len(pads) {
				target = pads[j]
			}
			if target > 0 && runewidth.StringWidth(Decolorise(cell)) > target {
				cell = textutil.Truncate(Decolorise(cell), target)
			}
			pad := 0
			if j < len(pads) {
				pad = pads[j] - runewidth.StringWidth(Decolorise(cell))
			}
			if pad < 0 {
				pad = 0
			}
			parts[j] = cell + strings.Repeat(" ", pad)
		}
		lines[i] = strings.Join(parts, " ")
	}
	return strings.Join(lines, "\n")
}

// PadCell right-pads a cell to width (visible width).
func PadCell(cell string, width int) string {
	pad := width - runewidth.StringWidth(Decolorise(cell))
	if pad < 0 {
		pad = 0
	}
	return cell + strings.Repeat(" ", pad)
}
