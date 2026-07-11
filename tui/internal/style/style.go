package style

import (
	"github.com/charmbracelet/lipgloss"

	"github.com/butbeautifulv/egregore/tui/internal/textutil"
)

var (
	ColorPrimary   = lipgloss.Color("#7C3AED")
	ColorAccent    = lipgloss.Color("#22D3EE")
	ColorMuted     = lipgloss.Color("#6B7280")
	ColorSuccess   = lipgloss.Color("#34D399")
	ColorWarning   = lipgloss.Color("#FBBF24")
	ColorDanger    = lipgloss.Color("#F87171")
	ColorBg        = lipgloss.Color("#111827")
	ColorSurface   = lipgloss.Color("#1F2937")
	ColorBorder    = lipgloss.Color("#374151")
	ColorText      = lipgloss.Color("#F9FAFB")
	ColorTextMuted = lipgloss.Color("#9CA3AF")
)

func TitleStyle() lipgloss.Style {
	return lipgloss.NewStyle().Bold(true).Foreground(ColorPrimary)
}

func NavActiveStyle() lipgloss.Style {
	return lipgloss.NewStyle().Bold(true).Foreground(ColorAccent).Background(ColorSurface)
}

func NavStyle() lipgloss.Style {
	return lipgloss.NewStyle().Foreground(ColorTextMuted)
}

func StatusBarStyle() lipgloss.Style {
	return lipgloss.NewStyle().
		Foreground(ColorTextMuted).
		Background(ColorSurface).
		Padding(0, 1)
}

func ErrorStyle() lipgloss.Style {
	return lipgloss.NewStyle().Foreground(ColorDanger).Bold(true)
}

func SuccessStyle() lipgloss.Style {
	return lipgloss.NewStyle().Foreground(ColorSuccess)
}

func PanelStyle() lipgloss.Style {
	return lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(ColorBorder).
		Padding(0, 1)
}

func HelpStyle() lipgloss.Style {
	return lipgloss.NewStyle().Foreground(ColorTextMuted).Italic(true)
}

func Truncate(s string, max int) string {
	return textutil.Truncate(s, max)
}

// StatusStyle returns semantic color for work order / job status strings.
func StatusStyle(status string) lipgloss.Style {
	switch status {
	case "running", "in_progress":
		return lipgloss.NewStyle().Foreground(ColorSuccess)
	case "open", "active", "pending", "queued":
		return lipgloss.NewStyle().Foreground(ColorWarning)
	case "failed", "error", "cancelled":
		return lipgloss.NewStyle().Foreground(ColorDanger)
	case "completed", "done", "closed":
		return lipgloss.NewStyle().Foreground(ColorTextMuted)
	default:
		return lipgloss.NewStyle().Foreground(ColorText)
	}
}

func SectionTitleStyle() lipgloss.Style {
	return lipgloss.NewStyle().Foreground(ColorTextMuted).Bold(true)
}

func TabActiveStyle() lipgloss.Style {
	return lipgloss.NewStyle().Foreground(ColorAccent).Bold(true)
}

func TabInactiveStyle() lipgloss.Style {
	return lipgloss.NewStyle().Foreground(ColorTextMuted)
}

func SelectedRowStyle() lipgloss.Style {
	return lipgloss.NewStyle().Foreground(ColorAccent).Bold(true)
}

// SectionFrameStyle colors manual section and pane frame glyphs.
func SectionFrameStyle(active bool) lipgloss.Style {
	color := ColorBorder
	if active {
		color = ColorAccent
	}
	return lipgloss.NewStyle().Foreground(color)
}
