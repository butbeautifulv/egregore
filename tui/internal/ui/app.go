package ui

import (
	tea "github.com/charmbracelet/bubbletea"

	"github.com/butbeautifulv/egregore/tui/internal/config"
	"github.com/butbeautifulv/egregore/tui/internal/style"
	"github.com/butbeautifulv/egregore/tui/internal/ui/console"
	"github.com/butbeautifulv/egregore/tui/internal/ui/legacy"
)

// Model is the root application model.
type Model struct {
	cfg      config.Config
	showHelp bool
	width    int
	height   int

	console console.Model
	legacy  legacy.Model
}

func NewModel(cfg config.Config) Model {
	m := Model{cfg: cfg}
	if cfg.ConsoleLayout {
		m.console = console.New(cfg)
	} else {
		m.legacy = legacy.New(cfg)
	}
	return m
}

func (m Model) Init() tea.Cmd {
	if m.cfg.ConsoleLayout {
		return tea.Batch(m.console.Init(), tea.EnterAltScreen)
	}
	return m.legacy.Init()
}

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
	}

	if m.showHelp {
		if key, ok := msg.(tea.KeyMsg); ok {
			if key.String() == "f1" || key.String() == "esc" {
				m.showHelp = false
				return m, nil
			}
		}
		return m, nil
	}

	if m.cfg.ConsoleLayout {
		if key, ok := msg.(tea.KeyMsg); ok {
			switch key.String() {
			case "ctrl+c", "q":
				return m, tea.Quit
			case "f1", "?":
				m.showHelp = true
				return m, nil
			}
		}
		var cmd tea.Cmd
		m.console, cmd = m.console.Update(msg)
		return m, cmd
	}

	if key, ok := msg.(tea.KeyMsg); ok {
		switch key.String() {
		case "ctrl+c", "q":
			return m, tea.Quit
		case "f1":
			m.showHelp = true
			return m, nil
		}
	}

	var cmd tea.Cmd
	m.legacy, cmd = m.legacy.Update(msg)
	return m, cmd
}

func (m Model) View() string {
	if m.showHelp {
		if m.cfg.ConsoleLayout {
			return renderConsoleHelp(m.width, m.height)
		}
		return m.legacy.RenderHelp(m.width, m.height)
	}
	if m.cfg.ConsoleLayout {
		return m.console.View()
	}
	return m.legacy.View()
}

func renderConsoleHelp(width, height int) string {
	text := `Egregore Operator Console — keybindings

Layout
  Tab       Switch left panel ↔ right detail
  Esc       Back to left panel (from detail)
  1-5       Jump to left section (Status / WO / Approvals / Queues / Catalog)
  ? / F1    This help
  q         Quit

Work orders (section 2)
  ↑↓ j/k    Select row
  g/G       Jump top/bottom
  Enter     Open detail (Chat tab)
  n         New work order overlay
  r         Refresh list

Detail panel (right)
  ←→ [ ]    Switch tabs: Chat · Jobs · Findings · Intake
  PgUp/Dn   Scroll
  r         Toggle reasoning (Chat tab)
  a/x       HITL approve/reject (Chat tab)
  m         Follow-up composer (Chat tab, closed WO)
  Ctrl+Enter  Send follow-up

Approvals (section 3)
  Enter     Open related work order
  a/x       Approve/reject (y confirm)

Catalog (section 5)
  a/t/s/p/m or ←→   Sub-tabs
  Enter     Show detail in right panel
  /         Filter memory

Press F1, ? or Esc to close.`
	return style.PanelStyle().
		Width(min(width-2, 72)).
		Height(min(height-2, 28)).
		Render(text)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
