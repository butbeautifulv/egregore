package console

import (
	"strings"
	"testing"

	"github.com/charmbracelet/lipgloss"

	"github.com/butbeautifulv/egregore/tui/internal/config"
	"github.com/butbeautifulv/egregore/tui/internal/layout"
)

func TestRenderLeftSmallTerminalHasContent(t *testing.T) {
	m := New(config.Config{TenantID: "demo"})
	m.section = SectionWorkOrders
	m.width = 80
	m.height = 24

	left, _, _ := layout.OperatorConsoleLayout(m.width, m.height, layout.DefaultLeftPanelRatio)
	innerW := max(10, left.Width)
	innerH := left.Height
	out := m.renderLeft(innerW, innerH)
	if strings.TrimSpace(out) == "" {
		t.Fatal("renderLeft produced empty output")
	}
	if !strings.Contains(out, "Work orders") && !strings.Contains(out, "5") {
		t.Fatalf("missing work orders section: %q", out[:min(120, len(out))])
	}
}

func TestRenderViewFitsTerminal(t *testing.T) {
	m := New(config.Config{TenantID: "demo"})
	m.width = 80
	m.height = 24
	out := m.View()
	lines := strings.Split(out, "\n")
	if len(lines) > m.height {
		t.Fatalf("output lines %d exceed height %d", len(lines), m.height)
	}
	for i, line := range lines {
		if lipgloss.Width(line) > m.width {
			t.Fatalf("line %d width %d exceeds %d", i, lipgloss.Width(line), m.width)
		}
	}
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
