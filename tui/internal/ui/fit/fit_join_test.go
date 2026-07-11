package fit

import (
	"strings"
	"testing"

	"github.com/charmbracelet/lipgloss"
)

func TestPadLineExactWidth(t *testing.T) {
	out := PadLine(20, "hello")
	if lipgloss.Width(out) != 20 {
		t.Fatalf("width %d want 20", lipgloss.Width(out))
	}
}

func TestJoinHorizontalPanesNoBleed(t *testing.T) {
	left := strings.Repeat("L", 40)
	right := strings.Repeat("R", 40)
	out := JoinHorizontalPanes(30, 30, 1, left, right)
	if lipgloss.Width(out) != 60 {
		t.Fatalf("joined width %d want 60", lipgloss.Width(out))
	}
}
