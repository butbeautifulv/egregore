package fit

import (
	"strings"

	"github.com/charmbracelet/lipgloss"

	"github.com/butbeautifulv/egregore/tui/internal/textutil"
)

// Line truncates or soft-wraps plain text to the terminal width.
func Line(width int, text string) string {
	if width <= 0 {
		return text
	}
	if lipgloss.Width(text) <= width {
		return text
	}
	return textutil.WrapBlock(text, width)
}

// Plain truncates unstyled text to width display columns.
func Plain(width int, text string) string {
	if width <= 0 {
		return text
	}
	return textutil.Truncate(text, width)
}

// ClipLine truncates a single line (ANSI-safe) to width display columns.
func ClipLine(width int, text string) string {
	if width <= 0 {
		return ""
	}
	if lipgloss.Width(text) <= width {
		return text
	}
	return textutil.Truncate(text, width)
}

// PadLine clips then right-pads a line to exactly width display columns.
func PadLine(width int, line string) string {
	if width <= 0 {
		return ""
	}
	line = ClipLine(width, line)
	pad := width - lipgloss.Width(line)
	if pad > 0 {
		line += strings.Repeat(" ", pad)
	}
	return line
}

// JoinHorizontalPanes places two panes side by side with fixed per-line widths.
func JoinHorizontalPanes(leftW, rightW, height int, left, right string) string {
	if height <= 0 {
		return ""
	}
	leftLines := strings.Split(ClipBlock(leftW, height, left), "\n")
	rightLines := strings.Split(ClipBlock(rightW, height, right), "\n")
	var out []string
	for i := 0; i < height; i++ {
		l := ""
		r := ""
		if i < len(leftLines) {
			l = leftLines[i]
		}
		if i < len(rightLines) {
			r = rightLines[i]
		}
		out = append(out, PadLine(leftW, l)+PadLine(rightW, r))
	}
	return strings.Join(out, "\n")
}

// ClipBlock trims multiline ANSI content to at most width×height display cells.
func ClipBlock(width, height int, content string) string {
	if height <= 0 {
		return ""
	}
	if width <= 0 {
		width = 80
	}
	lines := strings.Split(content, "\n")
	if len(lines) > height {
		lines = lines[:height]
	}
	out := make([]string, len(lines))
	for i, line := range lines {
		out[i] = ClipLine(width, line)
	}
	return strings.Join(out, "\n")
}

// FitBlock clips then pads content to exactly width×height display cells.
func FitBlock(width, height int, content string) string {
	if height <= 0 {
		return ""
	}
	lines := strings.Split(ClipBlock(width, height, content), "\n")
	for len(lines) < height {
		lines = append(lines, PadLine(width, ""))
	}
	if len(lines) > height {
		lines = lines[:height]
	}
	return strings.Join(lines, "\n")
}

// ComposeFrame pads or clips content to exactly width×height lines (full terminal redraw).
func ComposeFrame(width, height int, content string) string {
	if height <= 0 {
		return ""
	}
	if width <= 0 {
		width = 80
	}
	lines := strings.Split(content, "\n")
	if len(lines) > height {
		lines = lines[:height]
	}
	out := make([]string, height)
	for i := 0; i < height; i++ {
		line := ""
		if i < len(lines) {
			line = lines[i]
		}
		out[i] = PadLine(width, line)
	}
	return strings.Join(out, "\n")
}
