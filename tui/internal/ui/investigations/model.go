package investigations

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/table"
	"github.com/charmbracelet/bubbles/textarea"
	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"

	"github.com/butbeautifulv/egregore/tui/internal/api"
	"github.com/butbeautifulv/egregore/tui/internal/style"
	"github.com/butbeautifulv/egregore/tui/internal/ui/fit"
	"github.com/butbeautifulv/egregore/tui/internal/ui/tableutil"
)

type Screen int

const (
	ScreenList Screen = iota
	ScreenNew
)

type investigationsLoadedMsg struct {
	items []api.InvestigationSummary
	infra *api.InfraHealthResponse
	err   error
}

type engagementCreatedMsg struct {
	id  string
	err error
}

type tickMsg time.Time

// Model is the investigations list screen.
type Model struct {
	client     *api.Client
	width      int
	height     int
	screen     Screen
	table      table.Model
	textarea   textarea.Model
	incidentID textinput.Model
	colSpecs   []tableutil.ColumnSpec
	items      []api.InvestigationSummary
	infra      *api.InfraHealthResponse
	err        string
	loading    bool
	creating   bool
	cursor     int
}

var investigationsColSpecs = []tableutil.ColumnSpec{
	{Title: "Goal", MinWidth: 12, Weight: 3},
	{Title: "Status", MinWidth: 8, Weight: 0},
	{Title: "Updated", MinWidth: 10, Weight: 0},
	{Title: "Personas", MinWidth: 8, Weight: 1},
}

func New(client *api.Client) Model {
	t := table.New(
		table.WithFocused(true),
		table.WithHeight(10),
	)
	t.SetStyles(tableutil.CompactStyles())

	ta := textarea.New()
	ta.Placeholder = "Describe the work order goal…"
	ta.CharLimit = 4000
	ta.SetWidth(60)
	ta.SetHeight(6)
	ta.ShowLineNumbers = false
	ta.Focus()

	inc := textinput.New()
	inc.Placeholder = "INC-2026-0042 (optional)"
	inc.CharLimit = 128
	inc.Width = 40

	return Model{
		client:     client,
		screen:     ScreenList,
		table:      t,
		textarea:   ta,
		incidentID: inc,
		colSpecs: investigationsColSpecs,
		loading:  true,
	}
}

func (m Model) Init() tea.Cmd {
	return tea.Batch(loadInvestigations(m.client), tickCmd())
}

func tickCmd() tea.Cmd {
	return tea.Tick(30*time.Second, func(t time.Time) tea.Msg { return tickMsg(t) })
}

func loadInvestigations(client *api.Client) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
		defer cancel()
		items, err := client.ListWorkOrders(ctx, 50)
		infra, infraErr := client.GetHealthInfra(ctx)
		if err != nil {
			return investigationsLoadedMsg{err: err}
		}
		if infraErr != nil {
			infra = nil
		}
		return investigationsLoadedMsg{items: items, infra: infra}
	}
}

func createEngagement(client *api.Client, goal, incidentID string) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
		defer cancel()
		intake := map[string]interface{}{}
		if strings.TrimSpace(incidentID) != "" {
			intake["incident_id"] = strings.TrimSpace(incidentID)
		}
		if strings.TrimSpace(goal) != "" {
			intake["goal"] = strings.TrimSpace(goal)
		}
		eng, err := client.CreateWorkOrderWithIntake(ctx, goal, intake)
		if err != nil {
			return engagementCreatedMsg{err: err}
		}
		id := eng.WorkOrderID
		if id == "" {
			id = eng.EngagementID
		}
		return engagementCreatedMsg{id: id}
	}
}

func (m Model) Update(msg tea.Msg) (Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		m.applyLayout()
		m.textarea.SetWidth(max(40, msg.Width-6))
		return m, nil

	case tickMsg:
		return m, tea.Batch(loadInvestigations(m.client), tickCmd())

	case investigationsLoadedMsg:
		m.loading = false
		if msg.err != nil {
			m.err = msg.err.Error()
			return m, nil
		}
		m.err = ""
		m.items = msg.items
		m.infra = msg.infra
		m.applyLayout()
		return m, nil

	case engagementCreatedMsg:
		m.creating = false
		if msg.err != nil {
			m.err = msg.err.Error()
			m.screen = ScreenList
			return m, nil
		}
		return m, tea.Batch(
			func() tea.Msg { return OpenWatchMsg{ID: msg.id} },
			loadInvestigations(m.client),
		)

	case tea.KeyMsg:
		if m.screen == ScreenNew {
			return m.updateNew(msg)
		}
		return m.updateList(msg)
	}

	return m, nil
}

// InputActive reports whether a text field is focused (global shortcuts disabled).
func (m Model) InputActive() bool {
	return m.screen == ScreenNew
}

func (m Model) updateList(msg tea.KeyMsg) (Model, tea.Cmd) {
	switch msg.String() {
	case "n":
		m.screen = ScreenNew
		m.textarea.SetValue("")
		m.incidentID.SetValue("")
		m.textarea.Focus()
		m.err = ""
		return m, textarea.Blink
	case "r":
		m.loading = true
		return m, loadInvestigations(m.client)
	case "enter":
		if len(m.items) == 0 {
			return m, nil
		}
		idx := m.table.Cursor()
		if idx >= 0 && idx < len(m.items) {
			return m, func() tea.Msg { return OpenWatchMsg{ID: m.items[idx].InvestigationID} }
		}
	}
	var cmd tea.Cmd
	m.table, cmd = tableutil.UpdateWrap(m.table, msg, len(m.items))
	return m, cmd
}

func (m Model) updateNew(msg tea.KeyMsg) (Model, tea.Cmd) {
	switch msg.String() {
	case "esc":
		m.screen = ScreenList
		m.table.Focus()
		return m, nil
	case "ctrl+s", "ctrl+enter":
		goal := strings.TrimSpace(m.textarea.Value())
		incident := strings.TrimSpace(m.incidentID.Value())
		if goal == "" && incident == "" {
			return m, nil
		}
		m.creating = true
		m.screen = ScreenList
		m.table.Focus()
		return m, createEngagement(m.client, goal, incident)
	}
	var cmd tea.Cmd
	m.textarea, cmd = m.textarea.Update(msg)
	var incCmd tea.Cmd
	m.incidentID, incCmd = m.incidentID.Update(msg)
	return m, tea.Batch(cmd, incCmd)
}

func (m *Model) applyLayout() {
	w := m.width
	if w <= 0 {
		w = 80
	}
	h := m.height
	tableH := 10
	if h > 0 {
		tableH = max(6, h-12)
	}
	tableutil.ApplyLayout(&m.table, w, tableH, m.colSpecs)
	m.rebuildTable()
}

func (m *Model) rebuildTable() {
	widths := tableutil.Widths(m.table.Columns())
	if len(widths) < 4 {
		widths = []int{40, 10, 14, 10}
	}
	rows := make([]table.Row, 0, len(m.items))
	for _, item := range m.items {
		personas := strings.Join(item.CompletedPersonas, ", ")
		rows = append(rows, table.Row{
			style.Truncate(item.Goal, widths[0]),
			style.Truncate(item.Status, widths[1]),
			style.Truncate(item.UpdatedAt, widths[2]),
			style.Truncate(personas, widths[3]),
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
	title := fmt.Sprintf("Work orders (%d)", len(m.items))
	b.WriteString(style.TitleStyle().Render(fit.Plain(w, title)))
	b.WriteString("\n")
	if m.infra != nil {
		hint := m.infra.WorkersHint
		if m.infra.RunningJobs > 0 {
			hint = fmt.Sprintf("%s (%d jobs)", hint, m.infra.RunningJobs)
		}
		b.WriteString(style.HelpStyle().Render(fit.Plain(w, "Infra: "+hint)))
		b.WriteString("\n")
	}
	if m.err != "" {
		b.WriteString(style.ErrorStyle().Render(fit.Plain(w, m.err)))
		b.WriteString("\n")
	}
	if m.loading {
		b.WriteString(style.HelpStyle().Render("Loading…"))
		b.WriteString("\n")
	}
	if m.creating {
		b.WriteString(style.HelpStyle().Render("Starting work order…"))
		b.WriteString("\n")
	}

	switch m.screen {
	case ScreenNew:
		panelW := max(20, w-4)
		b.WriteString(style.PanelStyle().Width(panelW).MaxWidth(panelW).Render(
			"New work order\n\n" +
				"Incident ID (optional):\n" + m.incidentID.View() + "\n\n" +
				"Goal:\n" + m.textarea.View() + "\n\n" +
				style.HelpStyle().Render("Ctrl+S / Ctrl+Enter submit · Esc cancel"),
		))
	default:
		if !m.loading && len(m.items) == 0 && m.err == "" {
			b.WriteString(style.HelpStyle().Render(fit.Line(w, "No work orders yet — press n to start")))
			b.WriteString("\n")
		}
		b.WriteString(m.table.View())
		b.WriteString("\n")
		b.WriteString(style.HelpStyle().Render(fit.Line(w, "↑/↓ j/k move · g/G top/end · enter watch · n new · r refresh")))
	}
	return b.String()
}

// OpenWatchMsg requests navigation to watch screen.
type OpenWatchMsg struct{ ID string }

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
