package components

import (
	"strings"

	"github.com/mattn/go-runewidth"

	"github.com/butbeautifulv/egregore/tui/internal/style"
	"github.com/butbeautifulv/egregore/tui/internal/textutil"
)

// RenderSectionTitle renders a lazydocker-style section header within width.
func RenderSectionTitle(name string, width int) string {
	if width <= 0 {
		width = 40
	}
	prefix := "─"
	plain := prefix + name
	visible := runewidth.StringWidth(plain)
	maxFill := width - visible
	if maxFill < 0 {
		return style.SectionTitleStyle().Render(textutil.Truncate(plain, width))
	}
	// Keep titles readable; do not span the entire panel with dashes.
	fill := maxFill
	if fill > 24 {
		fill = 24
	}
	if fill > 0 {
		plain += strings.Repeat("─", fill)
	}
	return style.SectionTitleStyle().Render(plain)
}
