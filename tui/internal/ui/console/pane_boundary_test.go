package console

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/butbeautifulv/egregore/tui/internal/config"
	"github.com/butbeautifulv/egregore/tui/internal/layout"
)

func TestPaneBoundaryWidths(t *testing.T) {
	m := New(config.Config{TenantID: "demo"})
	var cmd tea.Cmd
	m, cmd = m.Update(tea.WindowSizeMsg{Width: 100, Height: 30})
	_ = cmd
	if m.width != 100 {
		t.Fatalf("model width %d want 100", m.width)
	}
	out := m.View()
	lines := strings.Split(out, "\n")
	pl := layout.OperatorConsolePaneLayout(100, 30, layout.DefaultLeftPanelRatio)
	if pl.Left.Width+pl.Separator.Width+pl.Right.Width != 100 {
		t.Fatalf("layout sum %d", pl.Left.Width+pl.Separator.Width+pl.Right.Width)
	}
	for i, line := range lines {
		if w := lipgloss.Width(line); w != 100 {
			t.Errorf("line %d width=%d want 100", i, w)
		}
		if i == 0 && !strings.Contains(line, "┐") {
			t.Errorf("line %d missing right pane top border", i)
		}
	}
}

func TestViewSmallTerminal60x8(t *testing.T) {
	m := New(config.Config{TenantID: "demo"})
	m.width = 60
	m.height = 8
	out := m.View()
	assertExactTerminalSize(t, out, 60, 8)
}

func TestViewSmallTerminal80x10(t *testing.T) {
	m := New(config.Config{TenantID: "demo"})
	var cmd tea.Cmd
	m, cmd = m.Update(tea.WindowSizeMsg{Width: 80, Height: 10})
	_ = cmd
	out := m.View()
	assertExactTerminalSize(t, out, 80, 10)
}

func TestViewResizeNoOverflow(t *testing.T) {
	m := New(config.Config{TenantID: "demo"})
	var cmd tea.Cmd
	m, cmd = m.Update(tea.WindowSizeMsg{Width: 100, Height: 30})
	_ = cmd
	m.width = 60
	m.height = 8
	out := m.View()
	assertExactTerminalSize(t, out, 60, 8)
}

func assertExactTerminalSize(t *testing.T, out string, width, height int) {
	t.Helper()
	lines := strings.Split(out, "\n")
	if len(lines) != height {
		t.Fatalf("lines %d want %d", len(lines), height)
	}
	for i, line := range lines {
		if w := lipgloss.Width(line); w != width {
			t.Fatalf("line %d width %d want %d", i, w, width)
		}
	}
}
