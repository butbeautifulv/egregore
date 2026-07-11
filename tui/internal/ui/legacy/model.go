package legacy

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/butbeautifulv/egregore/tui/internal/api"
	"github.com/butbeautifulv/egregore/tui/internal/config"
	"github.com/butbeautifulv/egregore/tui/internal/style"
	"github.com/butbeautifulv/egregore/tui/internal/ui/approvals"
	"github.com/butbeautifulv/egregore/tui/internal/ui/catalog"
	"github.com/butbeautifulv/egregore/tui/internal/ui/fit"
	"github.com/butbeautifulv/egregore/tui/internal/ui/investigations"
	"github.com/butbeautifulv/egregore/tui/internal/ui/watch"
)

type globalTickMsg time.Time

type approvalBadgeMsg struct {
	count int
}

type Screen int

const (
	ScreenInvestigations Screen = iota
	ScreenWatch
	ScreenApprovals
	ScreenCatalog
)

// Model is the legacy full-screen navigation UI.
type Model struct {
	client      *api.Client
	cfg         config.Config
	screen      Screen
	width       int
	height      int
	lastWatchID string

	investigations investigations.Model
	watch          watch.Model
	approvals      approvals.Model
	catalog        catalog.Model
	approvalBadge  int
}

func New(cfg config.Config) Model {
	client := api.NewClient(cfg)
	return Model{
		client:         client,
		cfg:            cfg,
		screen:         ScreenInvestigations,
		investigations: investigations.New(client),
		watch:          watch.New(client, cfg.SSEEnabled),
		approvals:      approvals.New(client),
		catalog:        catalog.New(client),
	}
}

func (m Model) Init() tea.Cmd {
	return tea.Batch(
		m.investigations.Init(),
		m.approvals.Init(),
		m.catalog.Init(),
		tea.EnterAltScreen,
		globalTick(),
		pollApprovalBadge(m.client),
	)
}

func globalTick() tea.Cmd {
	return tea.Tick(15*time.Second, func(t time.Time) tea.Msg { return globalTickMsg(t) })
}

func pollApprovalBadge(client *api.Client) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
		defer cancel()
		items, err := client.ListPendingApprovals(ctx)
		if err != nil {
			return approvalBadgeMsg{count: 0}
		}
		return approvalBadgeMsg{count: len(items)}
	}
}

func (m Model) Update(msg tea.Msg) (Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		var cmds []tea.Cmd
		var cmd tea.Cmd
		m.investigations, cmd = m.investigations.Update(msg)
		cmds = append(cmds, cmd)
		m.watch, cmd = m.watch.Update(msg)
		cmds = append(cmds, cmd)
		m.approvals, cmd = m.approvals.Update(msg)
		cmds = append(cmds, cmd)
		m.catalog, cmd = m.catalog.Update(msg)
		cmds = append(cmds, cmd)
		return m, tea.Batch(cmds...)

	case investigations.OpenWatchMsg:
		m.lastWatchID = msg.ID
		m.screen = ScreenWatch
		return m, m.watch.SetInvestigationID(msg.ID)

	case globalTickMsg:
		return m, tea.Batch(globalTick(), pollApprovalBadge(m.client))

	case approvalBadgeMsg:
		m.approvalBadge = msg.count
		return m, nil

	case tea.KeyMsg:
		return m.handleKey(msg)

	default:
		return m.broadcast(msg)
	}
}

func (m Model) handleKey(msg tea.KeyMsg) (Model, tea.Cmd) {
	if m.inputActive() {
		switch msg.String() {
		case "ctrl+c":
			return m, tea.Quit
		}
		var cmd tea.Cmd
		switch m.screen {
		case ScreenInvestigations:
			m.investigations, cmd = m.investigations.Update(msg)
		case ScreenCatalog:
			m.catalog, cmd = m.catalog.Update(msg)
		}
		return m, cmd
	}

	switch msg.String() {
	case "ctrl+c", "q":
		return m, tea.Quit
	case "1":
		m.screen = ScreenInvestigations
		return m, nil
	case "2":
		m.screen = ScreenWatch
		if m.lastWatchID != "" {
			return m, m.watch.SetInvestigationID(m.lastWatchID)
		}
		return m, nil
	case "3":
		m.screen = ScreenApprovals
		return m, nil
	case "4":
		m.screen = ScreenCatalog
		return m, nil
	case "esc":
		if m.screen == ScreenWatch {
			m.screen = ScreenInvestigations
			return m, nil
		}
	}

	var cmd tea.Cmd
	switch m.screen {
	case ScreenInvestigations:
		m.investigations, cmd = m.investigations.Update(msg)
	case ScreenWatch:
		m.watch, cmd = m.watch.Update(msg)
	case ScreenApprovals:
		m.approvals, cmd = m.approvals.Update(msg)
	case ScreenCatalog:
		m.catalog, cmd = m.catalog.Update(msg)
	}
	return m, cmd
}

func (m Model) broadcast(msg tea.Msg) (Model, tea.Cmd) {
	var cmds []tea.Cmd
	var cmd tea.Cmd
	m.investigations, cmd = m.investigations.Update(msg)
	cmds = append(cmds, cmd)
	m.watch, cmd = m.watch.Update(msg)
	cmds = append(cmds, cmd)
	m.approvals, cmd = m.approvals.Update(msg)
	cmds = append(cmds, cmd)
	m.catalog, cmd = m.catalog.Update(msg)
	cmds = append(cmds, cmd)
	return m, tea.Batch(cmds...)
}

func (m Model) View() string {
	var body string
	switch m.screen {
	case ScreenInvestigations:
		body = m.investigations.View()
	case ScreenWatch:
		body = m.watch.View()
	case ScreenApprovals:
		body = m.approvals.View()
	case ScreenCatalog:
		body = m.catalog.View()
	}
	count := m.approvalBadge
	if m.screen == ScreenApprovals {
		count = m.approvals.PendingCount()
	}
	nav := renderNav(m.screen, count, m.width)
	status := renderStatusBar(m.width, m.cfg, nav)
	return strings.Join([]string{body, status}, "\n")
}

func (m Model) RenderHelp(width, height int) string {
	text := `Egregore Operator TUI (legacy) — keybindings

  1  Work orders   2  Watch   3  Approvals   4  Catalog
  F1 Help   q Quit

Set EGREGORE_TUI_CONSOLE=1 (default) for the operator console layout.`
	return style.PanelStyle().Width(min(width-2, 72)).Height(min(height-2, 12)).Render(text)
}

func (m Model) inputActive() bool {
	if m.screen == ScreenInvestigations && m.investigations.InputActive() {
		return true
	}
	if m.screen == ScreenCatalog && m.catalog.InputActive() {
		return true
	}
	return false
}

func renderStatusBar(width int, cfg config.Config, nav string) string {
	if width <= 0 {
		width = 80
	}
	navW := lipgloss.Width(nav)
	budget := width - navW - 2
	if budget < 0 {
		budget = 0
	}
	right := fit.Plain(budget, fmt.Sprintf("API: %s  tenant: %s", cfg.APIURL, cfg.TenantID))
	line := nav + "  " + right
	return style.StatusBarStyle().Width(width).MaxWidth(width).Render(line)
}

func renderNav(active Screen, approvalCount, width int) string {
	type navItem struct {
		screen      Screen
		long, short string
		badge       int
	}
	items := []navItem{
		{ScreenInvestigations, "1 Investigations", "1 Inv", 0},
		{ScreenWatch, "2 Watch", "2 Watch", 0},
		{ScreenApprovals, "3 Approvals", "3 Appr", approvalCount},
		{ScreenCatalog, "4 Catalog", "4 Cat", 0},
	}
	useShort := width > 0 && width < 96
	var parts []string
	for _, item := range items {
		label := item.long
		if useShort {
			label = item.short
		}
		if item.badge > 0 {
			label = fmt.Sprintf("%s [%d]", label, item.badge)
		}
		if item.screen == active {
			parts = append(parts, style.NavActiveStyle().Render(label))
		} else {
			parts = append(parts, style.NavStyle().Render(label))
		}
	}
	parts = append(parts, style.HelpStyle().Render("F1 · q"))
	sep := " │ "
	if width > 0 && width < 72 {
		sep = " "
	}
	return strings.Join(parts, sep)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
