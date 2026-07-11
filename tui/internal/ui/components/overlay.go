package components

import (
	"strings"

	"github.com/charmbracelet/lipgloss"

	"github.com/butbeautifulv/egregore/tui/internal/style"
	"github.com/butbeautifulv/egregore/tui/internal/ui/fit"
)

// RenderOverlay centers modal content over the main view.
func RenderOverlay(content string, width, height int) string {
	panel := style.PanelStyle().
		Width(min(width-4, 72)).
		MaxWidth(width - 4).
		Render(content)
	return lipgloss.Place(
		width, height,
		lipgloss.Center, lipgloss.Center,
		panel,
	)
}

// RenderOverlayOn composites a centered modal over existing body content.
func RenderOverlayOn(body, content string, width, height int) string {
	if width <= 0 || height <= 0 {
		return body
	}
	background := fit.FitBlock(width, height, body)
	foreground := RenderOverlay(content, width, height)
	bLines := strings.Split(background, "\n")
	fLines := strings.Split(fit.FitBlock(width, height, foreground), "\n")
	out := make([]string, height)
	for i := 0; i < height; i++ {
		b := ""
		f := ""
		if i < len(bLines) {
			b = bLines[i]
		}
		if i < len(fLines) {
			f = fLines[i]
		}
		if strings.TrimSpace(f) != "" {
			out[i] = fit.PadLine(width, f)
		} else {
			out[i] = fit.PadLine(width, b)
		}
	}
	return strings.Join(out, "\n")
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
