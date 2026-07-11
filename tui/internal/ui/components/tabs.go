package components

import (
	"strings"

	"github.com/charmbracelet/lipgloss"

	"github.com/butbeautifulv/egregore/tui/internal/style"
)

// RenderTabs renders text tabs with the active tab highlighted.
func RenderTabs(labels []string, active int, width int) string {
	if len(labels) == 0 {
		return ""
	}
	if active < 0 {
		active = 0
	}
	if active >= len(labels) {
		active = len(labels) - 1
	}
	if line := renderTabLine(labels, active, false); width <= 0 || lipgloss.Width(line) <= width {
		return line
	}
	short := shortenTabLabels(labels)
	if line := renderTabLine(short, active, false); lipgloss.Width(line) <= width {
		return line
	}
	// Last resort: show active tab only so it is never replaced by "…".
	activeLabel := short[active]
	return style.TabActiveStyle().Render(activeLabel)
}

func shortenTabLabels(labels []string) []string {
	out := make([]string, len(labels))
	for i, label := range labels {
		switch label {
		case "Findings":
			out[i] = "Find."
		default:
			out[i] = label
		}
	}
	return out
}

func renderTabLine(labels []string, active int, _ bool) string {
	var parts []string
	for i, label := range labels {
		if i == active {
			parts = append(parts, style.TabActiveStyle().Render(label))
		} else {
			parts = append(parts, style.TabInactiveStyle().Render(label))
		}
	}
	return strings.Join(parts, " · ")
}
