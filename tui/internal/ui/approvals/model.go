package approvals

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/table"
	tea "github.com/charmbracelet/bubbletea"

	"github.com/butbeautifulv/egregore/tui/internal/api"
	"github.com/butbeautifulv/egregore/tui/internal/style"
	"github.com/butbeautifulv/egregore/tui/internal/ui/fit"
	"github.com/butbeautifulv/egregore/tui/internal/ui/tableutil"
)

type loadedMsg struct {
	items []api.PendingApproval
	err   error
}

type actionMsg struct {
	err error
}

type tickMsg time.Time

// Model is the approvals list screen.
type Model struct {
	client        *api.Client
	width         int
	height        int
	table         table.Model
	colSpecs      []tableutil.ColumnSpec
	items         []api.PendingApproval
	err           string
	loading       bool
	confirmAction string
}

var approvalsColSpecs = []tableutil.ColumnSpec{
	{Title: "Persona", MinWidth: 8, Weight: 0},
	{Title: "Tool", MinWidth: 10, Weight: 2},
	{Title: "Risk", MinWidth: 6, Weight: 0},
	{Title: "Job ID", MinWidth: 10, Weight: 2},
}

func New(client *api.Client) Model {
	t := table.New(
		table.WithFocused(true),
		table.WithHeight(12),
	)
	t.SetStyles(tableutil.CompactStyles())

	return Model{client: client, table: t, colSpecs: approvalsColSpecs, loading: true}
}

func (m Model) Init() tea.Cmd {
	return tea.Batch(load(m.client), tick())
}

func load(client *api.Client) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
		defer cancel()
		items, err := client.ListPendingApprovals(ctx)
		return loadedMsg{items: items, err: err}
	}
}

func tick() tea.Cmd {
	return tea.Tick(15*time.Second, func(t time.Time) tea.Msg { return tickMsg(t) })
}

func (m Model) Update(msg tea.Msg) (Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		m.applyLayout()
		return m, nil

	case tickMsg:
		return m, tea.Batch(load(m.client), tick())

	case loadedMsg:
		m.loading = false
		if msg.err != nil {
			m.err = msg.err.Error()
			return m, nil
		}
		m.err = ""
		m.items = msg.items
		m.applyLayout()
		return m, nil

	case actionMsg:
		m.confirmAction = ""
		if msg.err != nil {
			m.err = msg.err.Error()
		} else {
			m.err = ""
		}
		return m, load(m.client)

	case tea.KeyMsg:
		if m.confirmAction != "" {
			return m.handleConfirm(msg)
		}
		switch msg.String() {
		case "r":
			m.loading = true
			return m, load(m.client)
		case "a":
			if len(m.items) > 0 {
				m.confirmAction = "approve"
			}
			return m, nil
		case "x":
			if len(m.items) > 0 {
				m.confirmAction = "reject"
			}
			return m, nil
		}
	}

	var cmd tea.Cmd
	m.table, cmd = tableutil.UpdateWrap(m.table, msg, len(m.items))
	return m, cmd
}

func (m Model) handleConfirm(msg tea.KeyMsg) (Model, tea.Cmd) {
	switch msg.String() {
	case "y":
		idx := m.table.Cursor()
		if idx < 0 || idx >= len(m.items) {
			m.confirmAction = ""
			return m, nil
		}
		approval := m.items[idx]
		decision := m.confirmAction
		client := m.client
		return m, func() tea.Msg {
			ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
			defer cancel()
			err := client.ResumeJob(ctx, approval.JobID, decision, approval.ApprovalID)
			return actionMsg{err: err}
		}
	case "n", "esc":
		m.confirmAction = ""
	}
	return m, nil
}

func (m *Model) applyLayout() {
	w := m.width
	if w <= 0 {
		w = 80
	}
	h := m.height
	tableH := 12
	if h > 0 {
		tableH = max(8, h-10)
	}
	tableutil.ApplyLayout(&m.table, w, tableH, m.colSpecs)
	m.rebuildTable()
}

func (m *Model) rebuildTable() {
	widths := tableutil.Widths(m.table.Columns())
	if len(widths) < 4 {
		widths = []int{10, 20, 8, 30}
	}
	rows := make([]table.Row, 0, len(m.items))
	for _, item := range m.items {
		rows = append(rows, table.Row{
			style.Truncate(item.Persona, widths[0]),
			style.Truncate(item.ToolName, widths[1]),
			style.Truncate(item.RiskLevel, widths[2]),
			style.Truncate(item.JobID, widths[3]),
		})
	}
	m.table.SetRows(rows)
}

func (m Model) View() string {
	var b strings.Builder
	w := m.width
	if w <= 0 {
		w = 80
	}
	title := "Approvals"
	if len(m.items) > 0 {
		title = fmt.Sprintf("Approvals (%d)", len(m.items))
	}
	b.WriteString(style.TitleStyle().Render(fit.Plain(w, title)))
	b.WriteString("\n")
	if m.err != "" {
		b.WriteString(style.ErrorStyle().Render(fit.Plain(w, m.err)))
		b.WriteString("\n")
	}
	if m.loading {
		b.WriteString(style.HelpStyle().Render("Loading…"))
		b.WriteString("\n")
	}
	if m.confirmAction != "" {
		b.WriteString(style.ErrorStyle().Render(fit.Plain(w, fmt.Sprintf("Confirm %s selected? y/n", m.confirmAction))))
		b.WriteString("\n")
	}
	if !m.loading && len(m.items) == 0 {
		b.WriteString(style.HelpStyle().Render("No pending approvals"))
		b.WriteString("\n")
	}
	b.WriteString(m.table.View())
	b.WriteString("\n")
	b.WriteString(style.HelpStyle().Render(fit.Line(w, "↑/↓ j/k move · a approve · x reject · r refresh")))
	return b.String()
}

func (m Model) PendingCount() int { return len(m.items) }

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
