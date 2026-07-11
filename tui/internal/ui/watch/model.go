package watch

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/textarea"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/butbeautifulv/egregore/tui/internal/api"
	"github.com/butbeautifulv/egregore/tui/internal/chat"
	"github.com/butbeautifulv/egregore/tui/internal/style"
	"github.com/butbeautifulv/egregore/tui/internal/ui/fit"
	"github.com/butbeautifulv/egregore/tui/internal/ui/sse"
)

type detailLoadedMsg struct {
	detail    *api.InvestigationDetail
	jobs      []api.JobSummary
	followUps []api.FollowUpTurn
	features  api.APIFeatures
	err       error
}

type followUpSentMsg struct {
	turns []api.FollowUpTurn
	err   error
}

type streamEventMsg struct {
	event api.EngagementStreamEvent
}

type streamStatusMsg struct {
	status api.StreamStatus
}

type statusStreamEventMsg struct {
	event api.StatusStreamEvent
}

type globalStreamStatusMsg struct {
	status api.StreamStatus
}

type pollTickMsg time.Time

type approvalActionMsg struct {
	err error
}

type showFindingsMsg struct{}

// Model watches a single investigation with SSE chat.
type Model struct {
	client         *api.Client
	sseEnabled     bool
	investigationID string
	width          int
	height         int
	detail         *api.InvestigationDetail
	jobs           []api.JobSummary
	chatState      *chat.State
	features       api.APIFeatures
	viewport       viewport.Model
	findingsVP     viewport.Model
	showFindings   bool
	showReasoning  bool
	streamStatus   api.StreamStatus
	globalStatus   api.StreamStatus
	approvals      []api.PendingApproval
	approvalIdx    int
	confirmAction  string // approve|reject
	followUps      []api.FollowUpTurn
	showComposer   bool
	composer       textarea.Model
	sendingFollow  bool
	err            string
	loading        bool
	streamCtx      context.Context
	streamCancel   context.CancelFunc
	seenKeys       map[string]bool
}

func New(client *api.Client, sseEnabled bool) Model {
	vp := viewport.New(80, 20)
	vp.Style = lipgloss.NewStyle()
	fvp := viewport.New(80, 10)
	ta := textarea.New()
	ta.Placeholder = "Follow-up message…"
	ta.SetWidth(72)
	ta.SetHeight(3)
	ta.ShowLineNumbers = false
	ta.CharLimit = 4000
	return Model{
		client:     client,
		sseEnabled: sseEnabled,
		chatState:  chat.NewState(),
		viewport:   vp,
		findingsVP: fvp,
		composer:   ta,
		seenKeys:   make(map[string]bool),
		loading:    true,
	}
}

func (m *Model) SetInvestigationID(id string) tea.Cmd {
	if m.streamCancel != nil {
		m.streamCancel()
	}
	m.investigationID = id
	m.chatState = chat.NewState()
	m.seenKeys = make(map[string]bool)
	m.loading = true
	m.err = ""
	m.streamStatus = api.StreamIdle
	m.globalStatus = api.StreamIdle

	ctx, cancel := context.WithCancel(context.Background())
	m.streamCtx = ctx
	m.streamCancel = cancel

	cmds := []tea.Cmd{
		loadDetail(m.client, id),
		loadApprovals(m.client),
		startEngagementStream(m, id),
		startStatusStream(m),
		pollTick(),
	}
	return tea.Batch(cmds...)
}

func loadDetail(client *api.Client, id string) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
		defer cancel()
		detail, err := client.GetInvestigation(ctx, id)
		if err != nil {
			return detailLoadedMsg{err: err}
		}
		jobs, jobsErr := client.GetInvestigationJobs(ctx, id)
		if jobsErr != nil {
			return detailLoadedMsg{detail: detail, err: jobsErr}
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
		return detailLoadedMsg{detail: detail, jobs: jobs, followUps: followUps, features: features}
	}
}

func loadApprovals(client *api.Client) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
		defer cancel()
		items, err := client.ListPendingApprovals(ctx)
		if err != nil {
			return approvalsLoadedMsg{err: err}
		}
		return approvalsLoadedMsg{items: items}
	}
}

type approvalsLoadedMsg struct {
	items []api.PendingApproval
	err   error
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
				sse.Send(streamEventMsg{event: event})
			},
			func(status api.StreamStatus) {
				sse.Send(streamStatusMsg{status: status})
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
				sse.Send(statusStreamEventMsg{event: event})
			},
			func(status api.StreamStatus) {
				sse.Send(globalStreamStatusMsg{status: status})
			},
		)
		return nil
	}
}

func pollTick() tea.Cmd {
	return tea.Tick(12*time.Second, func(t time.Time) tea.Msg { return pollTickMsg(t) })
}

func (m Model) Init() tea.Cmd { return nil }

func (m Model) Update(msg tea.Msg) (Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		chatH := max(8, msg.Height-14)
		findH := max(6, msg.Height/3)
		if m.showFindings {
			chatH = max(6, msg.Height-findH-14)
			m.findingsVP.Width = msg.Width - 4
			m.findingsVP.Height = findH
		}
		m.viewport.Width = msg.Width - 4
		m.viewport.Height = chatH
		m.refreshViewports()
		return m, nil

	case detailLoadedMsg:
		m.loading = false
		if msg.err != nil {
			m.err = msg.err.Error()
			return m, nil
		}
		m.detail = msg.detail
		m.jobs = msg.jobs
		m.followUps = msg.followUps
		m.features = msg.features
		m.chatState.HydrateFromDetail(m.detail, m.investigationID)
		m.refreshViewports()
		return m, nil

	case followUpSentMsg:
		m.sendingFollow = false
		if msg.err != nil {
			m.err = msg.err.Error()
			return m, nil
		}
		m.followUps = msg.turns
		m.showComposer = false
		m.composer.Reset()
		m.refreshViewports()
		return m, nil

	case streamEventMsg:
		key := chat.EventDedupeKey(msg.event)
		if m.seenKeys[key] {
			return m, nil
		}
		m.seenKeys[key] = true
		m.chatState.ApplyEvent(msg.event, m.features, m.investigationID)
		if msg.event.Type == "follow_up_complete" || msg.event.Type == "follow_up_failed" {
			return m, loadDetail(m.client, m.investigationID)
		}
		m.refreshViewports()
		if chat.ShouldRefreshOnEvent(msg.event) {
			return m, loadDetail(m.client, m.investigationID)
		}
		return m, nil

	case streamStatusMsg:
		m.streamStatus = msg.status
		return m, nil

	case statusStreamEventMsg:
		if api.MatchesInvestigation(msg.event, m.investigationID) {
			return m, loadDetail(m.client, m.investigationID)
		}
		return m, nil

	case globalStreamStatusMsg:
		m.globalStatus = msg.status
		return m, nil

	case approvalsLoadedMsg:
		if msg.err == nil {
			m.approvals = filterApprovalsForInvestigation(msg.items, m.jobs)
		}
		return m, nil

	case approvalActionMsg:
		m.confirmAction = ""
		if msg.err != nil {
			m.err = msg.err.Error()
		} else {
			m.err = ""
		}
		return m, tea.Batch(loadApprovals(m.client), loadDetail(m.client, m.investigationID))

	case pollTickMsg:
		if m.detail != nil && !chat.IsInvestigationTerminal(m.detail, m.jobs) {
			if m.streamStatus != api.StreamOpen && m.globalStatus != api.StreamOpen {
				return m, loadDetail(m.client, m.investigationID)
			}
		}
		return m, pollTick()

	case tea.KeyMsg:
		if m.showComposer {
			return m.handleComposer(msg)
		}
		if m.confirmAction != "" {
			return m.handleConfirm(msg)
		}
		switch msg.String() {
		case "m":
			if m.detail != nil && m.detail.Status == "closed" {
				m.showComposer = !m.showComposer
				if m.showComposer {
					m.composer.Focus()
				} else {
					m.composer.Blur()
				}
			}
			return m, nil
		case "f":
			m.showFindings = !m.showFindings
			return m, nil
		case "r":
			m.showReasoning = !m.showReasoning
			m.refreshViewports()
			return m, nil
		case "a":
			if len(m.approvals) > 0 {
				m.confirmAction = "approve"
			}
			return m, nil
		case "x":
			if len(m.approvals) > 0 {
				m.confirmAction = "reject"
			}
			return m, nil
		}
	}

	var cmd tea.Cmd
	if m.showFindings {
		m.findingsVP, cmd = m.findingsVP.Update(msg)
	} else {
		m.viewport, cmd = m.viewport.Update(msg)
	}
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
			return approvalActionMsg{err: err}
		}
	case "n", "esc":
		m.confirmAction = ""
	}
	return m, nil
}

func (m *Model) refreshViewports() {
	opts := chat.RenderOptions{ShowReasoning: m.showReasoning, Width: m.viewport.Width}
	content := chat.RenderChat(m.detail, m.chatState, m.jobs, m.followUps, opts)
	m.viewport.SetContent(content)
	m.viewport.GotoBottom()

	findings := chat.RenderFindings(m.detail, m.findingsVP.Width)
	m.findingsVP.SetContent(findings)
}

func (m Model) handleComposer(msg tea.KeyMsg) (Model, tea.Cmd) {
	switch msg.String() {
	case "esc":
		m.showComposer = false
		m.composer.Blur()
		return m, nil
	case "ctrl+enter", "alt+enter":
		text := strings.TrimSpace(m.composer.Value())
		if text == "" || m.sendingFollow || m.investigationID == "" {
			return m, nil
		}
		m.sendingFollow = true
		client := m.client
		id := m.investigationID
		return m, func() tea.Msg {
			ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
			defer cancel()
			if _, err := client.SendFollowUp(ctx, id, text); err != nil {
				return followUpSentMsg{err: err}
			}
			turns, err := client.ListFollowUps(ctx, id)
			return followUpSentMsg{turns: turns, err: err}
		}
	}
	var cmd tea.Cmd
	m.composer, cmd = m.composer.Update(msg)
	return m, cmd
}

func (m Model) View() string {
	w := m.width
	if w <= 0 {
		w = 80
	}
	if m.investigationID == "" {
		return style.HelpStyle().Render(fit.Line(w, "Select an investigation (Enter on list) or press 2 after opening one."))
	}
	var b strings.Builder
	title := fit.Plain(w-12, "Watch: "+m.investigationID)
	b.WriteString(style.TitleStyle().Render(title))
	b.WriteString("  ")
	streamLabel := "○ poll"
	if m.streamStatus == api.StreamOpen || m.globalStatus == api.StreamOpen {
		streamLabel = "● live"
	}
	b.WriteString(style.SuccessStyle().Render(streamLabel))
	b.WriteString("\n")
	if m.detail != nil && len(m.detail.Intake) > 0 {
		if incident, ok := m.detail.Intake["incident_id"].(string); ok && strings.TrimSpace(incident) != "" {
			b.WriteString(style.HelpStyle().Render(fit.Plain(w, "Intake incident: "+incident)))
			b.WriteString("\n")
		}
	}
	if m.detail != nil && strings.TrimSpace(m.detail.ProfileID) != "" {
		b.WriteString(style.HelpStyle().Render(fit.Plain(w, "Profile: "+m.detail.ProfileID)))
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
	panelW := max(20, w-2)
	if len(m.approvals) > 0 {
		a := m.approvals[m.approvalIdx]
		hitl := fit.Plain(panelW-4, fmt.Sprintf(
			"HITL: %s wants %s (%s) — a approve · x reject",
			a.Persona, a.ToolName, a.RiskLevel,
		))
		b.WriteString(style.PanelStyle().Width(panelW).MaxWidth(panelW).Render(hitl))
		b.WriteString("\n")
	}
	if m.confirmAction != "" {
		b.WriteString(style.ErrorStyle().Render(fit.Plain(w, fmt.Sprintf("Confirm %s? y/n", m.confirmAction))))
		b.WriteString("\n")
	}
	b.WriteString(m.viewport.View())
	if m.showComposer {
		b.WriteString("\n")
		b.WriteString(style.PanelStyle().Width(panelW).MaxWidth(panelW).Render("Follow-up (Ctrl+Enter send, Esc cancel)\n" + m.composer.View()))
	}
	if m.showFindings {
		b.WriteString("\n")
		b.WriteString(style.PanelStyle().Width(panelW).MaxWidth(panelW).Render("Findings\n" + m.findingsVP.View()))
	}
	b.WriteString("\n")
	b.WriteString(style.HelpStyle().Render(fit.Line(w, "↑/↓ j/k scroll · f findings · m follow-up · r reasoning · a/x HITL · Esc back")))
	return b.String()
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
