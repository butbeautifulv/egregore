package fit

import (
	"strings"
	"testing"

	"github.com/charmbracelet/lipgloss"

	"github.com/butbeautifulv/egregore/tui/internal/style"
)

func TestFrameRightPaneExactSize(t *testing.T) {
	bodyH := 10
	rightW := 50
	inner := FitBlock(rightW-1, bodyH-2, strings.Repeat("y", rightW-1))
	border := style.SectionFrameStyle(false)
	out := FrameRightPane(rightW, bodyH, inner, border)
	if lipgloss.Height(out) != bodyH {
		t.Fatalf("height %d want %d", lipgloss.Height(out), bodyH)
	}
	lines := strings.Split(out, "\n")
	if !strings.Contains(lines[0], "┐") {
		t.Fatalf("missing top-right corner: %q", lines[0])
	}
	for i, line := range lines {
		if lipgloss.Width(line) != rightW {
			t.Fatalf("line %d width %d want %d: %q", i, lipgloss.Width(line), rightW, line)
		}
	}
}

func TestJoinOperatorPanesNoBleed(t *testing.T) {
	leftW, sepW, rightW, height := 30, 1, 30, 8
	leftInner := FitBlock(leftW, height, strings.Repeat("L", leftW))
	rightInner := FitBlock(rightW-1, height-2, strings.Repeat("R", rightW-1))
	sep := style.SectionFrameStyle(true)
	rightBorder := style.SectionFrameStyle(false)
	out := JoinOperatorPanes(leftW, sepW, rightW, height, leftInner, rightInner, sep, rightBorder)
	if lipgloss.Height(out) != height {
		t.Fatalf("height %d want %d", lipgloss.Height(out), height)
	}
	totalW := leftW + sepW + rightW
	for i, line := range strings.Split(out, "\n") {
		if lipgloss.Width(line) != totalW {
			t.Fatalf("line %d width %d want %d", i, lipgloss.Width(line), totalW)
		}
	}
}

func TestComposeFrameExactSize(t *testing.T) {
	out := ComposeFrame(40, 5, "hello\nworld")
	lines := strings.Split(out, "\n")
	if len(lines) != 5 {
		t.Fatalf("lines %d want 5", len(lines))
	}
	for i, line := range lines {
		if lipgloss.Width(line) != 40 {
			t.Fatalf("line %d width %d want 40", i, lipgloss.Width(line))
		}
	}
}
