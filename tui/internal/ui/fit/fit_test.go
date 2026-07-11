package fit

import (
	"strings"
	"testing"

	"github.com/charmbracelet/lipgloss"
)

func TestClipBlockLimitsSize(t *testing.T) {
	content := strings.Repeat("abcdefghij", 20) + "\n" +
		strings.Repeat("klmnopqrst", 20) + "\n" +
		"short\nextra line"
	out := ClipBlock(30, 2, content)
	lines := strings.Split(out, "\n")
	if len(lines) != 2 {
		t.Fatalf("line count: got %d want 2", len(lines))
	}
	for i, line := range lines {
		if lipgloss.Width(line) > 30 {
			t.Fatalf("line %d width %d exceeds 30", i, lipgloss.Width(line))
		}
	}
}

func TestClipLinePreservesShort(t *testing.T) {
	in := "hello"
	out := ClipLine(10, in)
	if out != in {
		t.Fatalf("got %q want %q", out, in)
	}
}

func TestClipLineTruncatesLong(t *testing.T) {
	in := strings.Repeat("x", 40)
	out := ClipLine(10, in)
	if lipgloss.Width(out) > 10 {
		t.Fatalf("width %d exceeds 10", lipgloss.Width(out))
	}
}
