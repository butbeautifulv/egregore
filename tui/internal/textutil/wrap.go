package textutil

import (
	"strings"
	"unicode/utf8"

	"github.com/mattn/go-runewidth"
)

// Truncate shortens s to fit max display columns without breaking UTF-8 runes.
func Truncate(s string, max int) string {
	if max <= 0 {
		return ""
	}
	if runewidth.StringWidth(s) <= max {
		return s
	}
	if max == 1 {
		return "…"
	}
	return runewidth.Truncate(s, max-1, "…")
}

// WrapLine truncates a single line to width display columns.
func WrapLine(line string, width int) string {
	return Truncate(line, width)
}

// WrapBlock word-wraps multiline text by display width (safe for Cyrillic/emoji).
func WrapBlock(text string, width int) string {
	if width <= 0 {
		return text
	}
	var out []string
	for _, line := range strings.Split(text, "\n") {
		for line != "" {
			if runewidth.StringWidth(line) <= width {
				out = append(out, line)
				break
			}
			n := breakIndex(line, width)
			out = append(out, line[:n])
			line = line[n:]
		}
	}
	return strings.Join(out, "\n")
}

func breakIndex(s string, width int) int {
	if width <= 0 {
		return utf8.RuneLen([]rune(s)[0])
	}
	w := 0
	n := 0
	for _, r := range s {
		rw := runewidth.RuneWidth(r)
		if w+rw > width {
			break
		}
		w += rw
		n += utf8.RuneLen(r)
	}
	if n == 0 {
		_, size := utf8.DecodeRuneInString(s)
		return size
	}
	return n
}
