package presentation

import (
	"strings"

	"github.com/butbeautifulv/egregore/tui/internal/style"
)

// FormatPair renders a two-column row that fits width display columns.
func FormatPair(left, right string, width int) string {
	if width <= 0 {
		return left + " " + right
	}
	if width < 12 {
		return style.Truncate(strings.TrimSpace(left+" "+right), width)
	}
	leftW := width * 2 / 5
	if leftW < 8 {
		leftW = 8
	}
	if leftW > width-4 {
		leftW = width / 2
	}
	rightW := width - leftW - 1
	return style.Truncate(left, leftW) + " " + style.Truncate(right, rightW)
}
