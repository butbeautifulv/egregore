package detail

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/textarea"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/butbeautifulv/egregore/tui/internal/api"
	"github.com/butbeautifulv/egregore/tui/internal/chat"
	"github.com/butbeautifulv/egregore/tui/internal/jsonfmt"
	"github.com/butbeautifulv/egregore/tui/internal/presentation"
	"github.com/butbeautifulv/egregore/tui/internal/style"
	"github.com/butbeautifulv/egregore/tui/internal/textutil"
	"github.com/butbeautifulv/egregore/tui/internal/ui/components"
	"github.com/butbeautifulv/egregore/tui/internal/ui/fit"
	"github.com/butbeautifulv/egregore/tui/internal/ui/sse"
)

// Tab is a right-panel detail tab.
type Tab int

const (
	TabChat Tab = iota
	TabJobs
	TabFindings
	TabIntake
	tabCount
)

func (t Tab) Label() string {
	switch t {
	case TabChat:
		return "Chat"
	case TabJobs:
		return "Jobs"
	case TabFindings:
		return "Findings"
	case TabIntake:
		return "Intake"
	default:
		return ""
	}
}

func AllTabLabels() []string {
	labels := make([]string, tabCount)
	for i := Tab(0); i < tabCount; i++ {
		labels[i] = i.Label()
	}
	return labels
}

type LoadedMsg struct {
	Detail    *api.InvestigationDetail
	Jobs      []api.JobSummary
	FollowUps []api.FollowUpTurn
	Features  api.APIFeatures
	Err       error
}

type FollowUpSentMsg struct {
	Turns []api.FollowUpTurn
	Err   error
}

type StreamEventMsg struct {
	Event api.EngagementStreamEvent
}

type StreamStatusMsg struct {
	Status api.StreamStatus
}

type StatusStreamEventMsg struct {
	Event api.StatusStreamEvent
}

type GlobalStreamStatusMsg struct {
	Status api.StreamStatus
}

type PollTickMsg time.Time

type ApprovalActionMsg struct {
	Err error
}

type ApprovalsLoadedMsg struct {
	Items []api.PendingApproval
	Err   error
}

// CatalogMode indicates catalog detail view in the right panel.
type CatalogMode int

const (
	CatalogNone CatalogMode = iota
	CatalogAgent
	CatalogSkill
	CatalogTool
	CatalogPlan
	CatalogMemory
)

// Model is the right-hand detail panel.
type Model struct {
	client         *api.Client
	sseEnabled     bool
	workOrderID    string
	width          int
	height         int
	tab            Tab
	detail         *api.InvestigationDetail
	jobs           []api.JobSummary
	followUps      []api.FollowUpTurn
	features       api.APIFeatures
	chatState      *chat.State
	viewport       viewport.Model
	showReasoning  bool
	streamStatus   api.StreamStatus
	globalStatus   api.StreamStatus
	approvals      []api.PendingApproval
	approvalIdx    int
	confirmAction  string
	composer       textarea.Model
	composerEditing bool
	sendingFollow  bool
	err            string
	loading        bool
	streamCtx      context.Context
	streamCancel   context.CancelFunc
	seenKeys       map[string]bool

	// Catalog detail
	catalogMode   CatalogMode
	catalogVP     viewport.Model
	catalogText   string
}

func New(client *api.Client, sseEnabled bool) Model {
	vp := viewport.New(80, 20)
	vp.Style = lipgloss.NewStyle()
	cvp := viewport.New(80, 20)
	ta := textarea.New()
	ta.Placeholder = "Ask a follow-up or add context for the agents…"
	ta.CharLimit = 4000
	ta.ShowLineNumbers = false
	return Model{
		client:     client,
		sseEnabled: sseEnabled,
		chatState:  chat.NewState(),
		viewport:   vp,
		catalogVP:  cvp,
		composer:   ta,
		seenKeys:   make(map[string]bool),
	}
}

func (m *Model) Load(workOrderID string) tea.Cmd {
	if m.streamCancel != nil {
		m.streamCancel()
	}
	m.workOrderID = workOrderID
	m.catalogMode = CatalogNone
	m.catalogText = ""
	m.chatState = chat.NewState()
	m.seenKeys = make(map[string]bool)
	m.loading = true
	m.err = ""
	m.tab = TabChat
	m.streamStatus = api.StreamIdle
	m.globalStatus = api.StreamIdle

	ctx, cancel := context.WithCancel(context.Background())
	m.streamCtx = ctx
	m.streamCancel = cancel

	return tea.Batch(
		loadDetail(m.client, workOrderID),
		loadApprovals(m.client),
		startEngagementStream(m, workOrderID),
		startStatusStream(m),
		pollTick(),
	)
}

func loadDetail(client *api.Client, id string) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
		defer cancel()
		detail, err := client.GetInvestigation(ctx, id)
		if err != nil {
			return LoadedMsg{Err: err}
		}
		jobs, jobsErr := client.GetInvestigationJobs(ctx, id)
		if jobsErr != nil {
			return LoadedMsg{Detail: detail, Err: jobsErr}
		}
		followUps, _ := client.ListFollowUps(ctx, id)
		health, _ := client.GetHealth(ctx)
		features := api.APIFeatures{StreamAgentOutput: true, StreamAgentTools: true}
		if health != nil {
			features = api.APIFeatures{
				StreamAgentOutput: health.Features.StreamAgentOutput,
				StreamAgentTools:  health.Features.StreamAgentTools,
			}
		}
		return LoadedMsg{Detail: detail, Jobs: jobs, FollowUps: followUps, Features: features}
	}
}

func loadApprovals(client *api.Client) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
		defer cancel()
		items, err := client.ListPendingApprovals(ctx)
		return ApprovalsLoadedMsg{Items: items, Err: err}
	}
}

func startEngagementStream(m *Model, id string) tea.Cmd {
	if !m.sseEnabled || id == "" {
		return nil
	}
	client := m.client
	ctx := m.streamCtx
	return func() tea.Msg {
		go api.RunEngagementStream(ctx, client, id,
			func(event api.EngagementStreamEvent) {
				sse.Send(StreamEventMsg{Event: event})
			},
			func(status api.StreamStatus) {
				sse.Send(StreamStatusMsg{Status: status})
			},
		)
		return nil
	}
}

func startStatusStream(m *Model) tea.Cmd {
	if !m.sseEnabled {
		return nil
	}
	client := m.client
	ctx := m.streamCtx
	return func() tea.Msg {
		go api.RunStatusStream(ctx, client,
			func(event api.StatusStreamEvent) {
				sse.Send(StatusStreamEventMsg{Event: event})
			},
			func(status api.StreamStatus) {
				sse.Send(GlobalStreamStatusMsg{Status: status})
			},
		)
		return nil
	}
}

func pollTick() tea.Cmd {
	return tea.Tick(12*time.Second, func(t time.Time) tea.Msg { return PollTickMsg(t) })
}

func (m Model) InputActive() bool {
	return m.tab == TabChat && m.composerEditing && CanComposeFollowUp(m.detail)
}

func (m Model) CurrentTab() Tab {
	return m.tab
}

func (m Model) CatalogModeActive() bool {
	return m.catalogMode != CatalogNone
}

func (m Model) StreamLive() bool {
	return m.streamStatus == api.StreamOpen || m.globalStatus == api.StreamOpen
}

func (m *Model) SetSize(width, height int) {
	m.width = width
	m.height = height
	innerW := max(10, width)
	m.applyLayoutHeights()
	m.viewport.Width = innerW
	m.catalogVP.Width = innerW
	m.catalogVP.Height = max(4, height-1)
	m.composer.SetWidth(max(20, innerW-4))
	m.composer.SetHeight(followUpComposerLines)
	m.refreshContent()
}

func (m *Model) syncFollowUpComposer() {
	if m.tab == TabChat && CanComposeFollowUp(m.detail) {
		m.composerEditing = true
		m.composer.Focus()
		return
	}
	m.composerEditing = false
	m.composer.Blur()
}

func (m *Model) applyLayoutHeights() {
	chrome := m.chromeBudget()
	m.viewport.Height = max(3, m.height-chrome.Total())
}

func (m Model) Update(msg tea.Msg) (Model, tea.Cmd) {
	switch msg := msg.(type) {
	case LoadedMsg:
		m.loading = false
		if msg.Err != nil {
			m.err = msg.Err.Error()
			return m, nil
		}
		m.detail = msg.Detail
		m.jobs = msg.Jobs
		m.followUps = msg.FollowUps
		m.features = msg.Features
		m.chatState.HydrateFromDetail(m.detail, m.workOrderID)
		m.syncFollowUpComposer()
		m.applyLayoutHeights()
		m.refreshContent()
		return m, nil

	case FollowUpSentMsg:
		m.sendingFollow = false
		if msg.Err != nil {
			m.err = msg.Err.Error()
			m.syncFollowUpComposer()
			m.refreshContent()
			return m, nil
		}
		m.followUps = msg.Turns
		m.composer.Reset()
		m.syncFollowUpComposer()
		m.refreshContent()
		return m, nil

	case StreamEventMsg:
		key := chat.EventDedupeKey(msg.Event)
		if m.seenKeys[key] {
			return m, nil
		}
		m.seenKeys[key] = true
		m.chatState.ApplyEvent(msg.Event, m.features, m.workOrderID)
		if msg.Event.Type == "follow_up_complete" || msg.Event.Type == "follow_up_failed" {
			return m, loadDetail(m.client, m.workOrderID)
		}
		m.refreshContent()
		if chat.ShouldRefreshOnEvent(msg.Event) {
			return m, loadDetail(m.client, m.workOrderID)
		}
		return m, nil

	case StreamStatusMsg:
		m.streamStatus = msg.Status
		return m, nil

	case StatusStreamEventMsg:
		if api.MatchesInvestigation(msg.Event, m.workOrderID) {
			return m, loadDetail(m.client, m.workOrderID)
		}
		return m, nil

	case GlobalStreamStatusMsg:
		m.globalStatus = msg.Status
		return m, nil

	case ApprovalsLoadedMsg:
		if msg.Err == nil {
			m.approvals = filterApprovalsForInvestigation(msg.Items, m.jobs)
		}
		return m, nil

	case ApprovalActionMsg:
		m.confirmAction = ""
		if msg.Err != nil {
			m.err = msg.Err.Error()
		} else {
			m.err = ""
		}
		return m, tea.Batch(loadApprovals(m.client), loadDetail(m.client, m.workOrderID))

	case PollTickMsg:
		if m.detail != nil && !chat.IsInvestigationTerminal(m.detail, m.jobs) {
			if m.streamStatus != api.StreamOpen && m.globalStatus != api.StreamOpen {
				return m, loadDetail(m.client, m.workOrderID)
			}
		}
		return m, pollTick()

	case tea.KeyMsg:
		if m.catalogMode != CatalogNone {
			return m.handleCatalogKeys(msg)
		}
		if m.composerEditing {
			return m.handleComposer(msg)
		}
		if m.confirmAction != "" {
			return m.handleConfirm(msg)
		}
		return m.handleKeys(msg)
	}

	var cmd tea.Cmd
	if m.catalogMode != CatalogNone {
		m.catalogVP, cmd = m.catalogVP.Update(msg)
	} else {
		m.viewport, cmd = m.viewport.Update(msg)
	}
	return m, cmd
}

func (m Model) handleKeys(msg tea.KeyMsg) (Model, tea.Cmd) {
	switch msg.String() {
	case "left", "[", "h":
		m.tab = Tab(int(m.tab)-1+int(tabCount)) % tabCount
		m.syncFollowUpComposer()
		m.applyLayoutHeights()
		m.refreshContent()
		return m, nil
	case "right", "]", "l":
		m.tab = Tab((int(m.tab) + 1) % int(tabCount))
		m.syncFollowUpComposer()
		m.applyLayoutHeights()
		m.refreshContent()
		return m, nil
	case "r":
		if m.tab == TabChat {
			m.showReasoning = !m.showReasoning
			m.refreshContent()
		}
		return m, nil
	case "m", "i":
		if m.tab == TabChat && CanComposeFollowUp(m.detail) {
			m.composerEditing = true
			m.composer.Focus()
		}
		return m, nil
	case "a":
		if len(m.approvals) > 0 && m.tab == TabChat {
			m.confirmAction = "approve"
		}
		return m, nil
	case "x":
		if len(m.approvals) > 0 && m.tab == TabChat {
			m.confirmAction = "reject"
		}
		return m, nil
	}
	var cmd tea.Cmd
	m.viewport, cmd = m.viewport.Update(msg)
	return m, cmd
}

func (m Model) handleCatalogKeys(msg tea.KeyMsg) (Model, tea.Cmd) {
	if msg.String() == "esc" {
		m.catalogMode = CatalogNone
		m.catalogText = ""
		return m, nil
	}
	var cmd tea.Cmd
	m.catalogVP, cmd = m.catalogVP.Update(msg)
	return m, cmd
}

func (m Model) handleConfirm(msg tea.KeyMsg) (Model, tea.Cmd) {
	switch msg.String() {
	case "y":
		if len(m.approvals) == 0 {
			m.confirmAction = ""
			return m, nil
		}
		approval := m.approvals[m.approvalIdx]
		decision := m.confirmAction
		client := m.client
		return m, func() tea.Msg {
			ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
			defer cancel()
			err := client.ResumeJob(ctx, approval.JobID, decision, approval.ApprovalID)
			return ApprovalActionMsg{Err: err}
		}
	case "n", "esc":
		m.confirmAction = ""
	}
	return m, nil
}

func (m Model) handleComposer(msg tea.KeyMsg) (Model, tea.Cmd) {
	switch msg.String() {
	case "esc":
		m.composerEditing = false
		m.composer.Blur()
		return m, nil
	case "ctrl+enter", "alt+enter":
		text := strings.TrimSpace(m.composer.Value())
		if text == "" || m.sendingFollow || m.workOrderID == "" {
			return m, nil
		}
		m.sendingFollow = true
		client := m.client
		id := m.workOrderID
		return m, func() tea.Msg {
			ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
			defer cancel()
			if _, err := client.SendFollowUp(ctx, id, text); err != nil {
				return FollowUpSentMsg{Err: err}
			}
			turns, err := client.ListFollowUps(ctx, id)
			return FollowUpSentMsg{Turns: turns, Err: err}
		}
	}
	var cmd tea.Cmd
	m.composer, cmd = m.composer.Update(msg)
	return m, cmd
}

func (m *Model) refreshContent() {
	if m.catalogMode != CatalogNone {
		m.catalogVP.SetContent(m.catalogText)
		return
	}
	switch m.tab {
	case TabChat:
		opts := chat.RenderOptions{ShowReasoning: m.showReasoning, Width: m.viewport.Width}
		content := chat.RenderChat(m.detail, m.chatState, m.jobs, m.followUps, opts)
		if len(m.approvals) > 0 {
			a := m.approvals[m.approvalIdx]
			banner := fmt.Sprintf("\n[HITL] %s wants %s (%s) — a approve · x reject\n",
				a.Persona, a.ToolName, a.RiskLevel)
			content += banner
		}
		if m.confirmAction != "" {
			content += fmt.Sprintf("\nConfirm %s? y/n\n", m.confirmAction)
		}
		m.viewport.SetContent(content)
		m.viewport.GotoBottom()
	case TabJobs:
		rows := [][]string{presentation.JobHeader()}
		for _, j := range m.jobs {
			rows = append(rows, presentation.JobCells(j))
		}
		m.viewport.SetContent(presentation.RenderTable(rows))
		m.viewport.GotoTop()
	case TabFindings:
		m.viewport.SetContent(chat.RenderFindings(m.detail, m.viewport.Width))
		m.viewport.GotoTop()
	case TabIntake:
		m.viewport.SetContent(renderIntake(m.detail, m.viewport.Width))
		m.viewport.GotoTop()
	}
}

func renderIntake(detail *api.InvestigationDetail, width int) string {
	if detail == nil {
		return "No work order selected."
	}
	var b strings.Builder
	if detail.ProfileID != "" {
		b.WriteString("Profile: " + detail.ProfileID + "\n")
	}
	if len(detail.Intake) > 0 {
		b.WriteString("\n--- Intake ---\n")
		b.WriteString(textutil.WrapBlock(jsonfmt.FormatValue(detail.Intake), width))
	} else {
		b.WriteString("No intake payload.\n")
	}
	return b.String()
}

func (m Model) View() string {
	w := m.width
	if w <= 0 {
		w = 80
	}
	h := m.height
	if h <= 0 {
		h = 24
	}
	var b strings.Builder
	if m.catalogMode != CatalogNone {
		b.WriteString(components.RenderTabs([]string{"Catalog detail"}, 0, w))
		b.WriteString("\n")
		b.WriteString(m.catalogVP.View())
		return fit.ClipBlock(w, h, b.String())
	}
	labels := AllTabLabels()
	b.WriteString(components.RenderTabs(labels, int(m.tab), w))
	b.WriteString("\n")
	if m.workOrderID == "" {
		b.WriteString(style.HelpStyle().Render("Select a work order (Enter on list)."))
		return fit.ClipBlock(w, h, b.String())
	}
	if m.err != "" {
		b.WriteString(style.ErrorStyle().Render(m.err))
		b.WriteString("\n")
	}
	if m.loading {
		b.WriteString(style.HelpStyle().Render("Loading…"))
		b.WriteString("\n")
	}
	b.WriteString(m.viewport.View())
	if m.tab == TabChat && m.workOrderID != "" {
		if panel := m.renderFollowUpComposerPanel(); panel != "" {
			b.WriteString("\n")
			b.WriteString(panel)
		}
	}
	return fit.ComposeFrame(w, h, b.String())
}

func (m *Model) ShowCatalogDetail(mode CatalogMode, text string) {
	m.catalogMode = mode
	m.catalogText = text
	m.catalogVP.SetContent(text)
	m.catalogVP.GotoTop()
}

func (m *Model) ClearCatalogDetail() {
	m.catalogMode = CatalogNone
	m.catalogText = ""
}

func filterApprovalsForInvestigation(all []api.PendingApproval, jobs []api.JobSummary) []api.PendingApproval {
	jobIDs := make(map[string]bool)
	for _, j := range jobs {
		jobIDs[j.JobID] = true
	}
	var out []api.PendingApproval
	for _, a := range all {
		if jobIDs[a.JobID] {
			out = append(out, a)
		}
	}
	return out
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

// FormatCatalogAgent builds agent detail text.
func FormatCatalogAgent(a *api.CatalogAgentDetail, w int) string {
	if a == nil {
		return ""
	}
	var b strings.Builder
	b.WriteString(fmt.Sprintf("Role: %s\n", a.Role))
	b.WriteString(fmt.Sprintf("Enabled: %t · Trust: %.0f%%\n", a.Enabled, a.EmpiricalTrust*100))
	if a.Description != "" {
		b.WriteString("\n" + textutil.WrapBlock(a.Description, w) + "\n")
	}
	b.WriteString("\n--- System Prompt ---\n")
	b.WriteString(textutil.WrapBlock(a.SystemPrompt, w))
	return b.String()
}

func FormatCatalogSkill(s *api.CatalogSkill, w int) string {
	if s == nil {
		return ""
	}
	var b strings.Builder
	if s.Name != "" {
		b.WriteString(s.Name + "\n")
	}
	b.WriteString(fmt.Sprintf("ID: %s · v%d", s.CatalogSkillID(), s.Version))
	if s.ApprovalStatus != "" {
		b.WriteString(" · " + s.ApprovalStatus)
	}
	if s.Description != "" {
		b.WriteString("\n\n" + textutil.WrapBlock(s.Description, w))
	}
	if s.Body != "" {
		b.WriteString("\n\n--- Body ---\n")
		b.WriteString(textutil.WrapBlock(s.Body, w))
	} else if s.Description == "" {
		b.WriteString("\n\n(no skill body)")
	}
	return b.String()
}

func FormatCatalogTool(t *api.CatalogTool, w int) string {
	if t == nil {
		return ""
	}
	raw, _ := json.MarshalIndent(t, "", "  ")
	return textutil.WrapBlock(string(raw), w)
}

func FormatCatalogPlan(p *api.CatalogPlan, w int) string {
	if p == nil {
		return ""
	}
	raw, _ := json.MarshalIndent(p, "", "  ")
	return textutil.WrapBlock(string(raw), w)
}

func FormatCatalogMemory(e *api.MemoryEntry, w int) string {
	if e == nil {
		return ""
	}
	var b strings.Builder
	b.WriteString(fmt.Sprintf("Agent: %s · Type: %s\n", e.SourceAgent, e.MemoryType))
	b.WriteString(textutil.WrapBlock(e.Content, w))
	return b.String()
}
