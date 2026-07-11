package tableutil

import (
	"github.com/charmbracelet/bubbles/table"
	"github.com/charmbracelet/lipgloss"

	"github.com/butbeautifulv/egregore/tui/internal/style"
)

// CompactStyles returns table styles that avoid per-cell borders and padding
// so column widths match the terminal budget.
func CompactStyles() table.Styles {
	s := table.DefaultStyles()
	s.Header = lipgloss.NewStyle().Bold(true).Foreground(style.ColorTextMuted).Padding(0, 0)
	s.Cell = lipgloss.NewStyle().Padding(0, 0)
	s.Selected = lipgloss.NewStyle().Foreground(style.ColorAccent).Bold(true).Padding(0, 0)
	return s
}
