package console

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/textarea"
	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"

	"github.com/butbeautifulv/egregore/tui/internal/api"
	"github.com/butbeautifulv/egregore/tui/internal/config"
	"github.com/butbeautifulv/egregore/tui/internal/layout"
	"github.com/butbeautifulv/egregore/tui/internal/presentation"
	"github.com/butbeautifulv/egregore/tui/internal/style"
	"github.com/butbeautifulv/egregore/tui/internal/ui/components"
	"github.com/butbeautifulv/egregore/tui/internal/ui/detail"
	"github.com/butbeautifulv/egregore/tui/internal/ui/fit"
	"github.com/butbeautifulv/egregore/tui/internal/ui/panels"
)

type tickMsg time.Time

type workOrdersLoadedMsg struct {
	items []api.InvestigationSummary
	err   error
}

type healthLoadedMsg struct {
	health *api.HealthResponse
	infra  *api.InfraHealthResponse
	err    error
}

type approvalsPanelMsg struct {
	items []api.PendingApproval
	err   error
}

type engagementCreatedMsg struct {
	id  string
	err error
}

type catalogLoadedMsg struct {
	agents []api.CatalogAgent
	tools  []api.CatalogTool
	skills []api.CatalogSkill
	plans  []api.CatalogPlan
	memory []api.MemoryEntry
	err    error
}

type catalogDetailLoadedMsg struct {
	mode detail.CatalogMode
	text string
	err  error
}

type openWOMsg struct {
	id  string
	err error
}

type approvalActionMsg struct {
	err error
}

// CatalogTab is the catalog sub-tab in the left panel.
type CatalogTab int

const (
	CatalogAgents CatalogTab = iota
	CatalogSkills
	CatalogMemory
	CatalogTools
	CatalogPlans
	catalogTabCount
)

func (t CatalogTab) Label() string {
	switch t {
	case CatalogAgents:
		return "Agents"
	case CatalogSkills:
		return "Skills"
	case CatalogMemory:
		return "Memory"
	case CatalogTools:
		return "Tools"
	case CatalogPlans:
		return "Plans"
	default:
		return ""
	}
}

func catalogTabLabels() []string {
	out := make([]string, catalogTabCount)
	for i := CatalogTab(0); i < catalogTabCount; i++ {
		out[i] = i.Label()
	}
	return out
}

// Model is the unified operator console.
type Model struct {
	client *api.Client
	cfg    config.Config

	width  int
	height int
	focus  FocusArea
	section LeftSection

	detail detail.Model

	workOrders   []api.InvestigationSummary
	woCursor     int
	woLoading    bool
	woErr        string

	health *api.HealthResponse
	infra  *api.InfraHealthResponse

	approvals      []api.PendingApproval
	approvalCursor int
	confirmAction  string

	catalogTab     CatalogTab
	catalogCursor  int
	catalogAgents  []api.CatalogAgent
	catalogTools   []api.CatalogTool
	catalogSkills  []api.CatalogSkill
	catalogPlans   []api.CatalogPlan
	catalogMemory  []api.MemoryEntry
	catalogLoading bool
	catalogErr     string
	memoryFilter   string
	filtering      bool
	filterInput    textinput.Model

	overlayOpen bool
	newGoal     textarea.Model
	newIncident textinput.Model
	creating    bool

	selectedWO string
	err        string
}

func New(cfg config.Config) Model {
	client := api.NewClient(cfg)
	ta := textarea.New()
	ta.Placeholder = "Describe the work order goal…"
	ta.CharLimit = 4000
	ta.ShowLineNumbers = false
	inc := textinput.New()
	inc.Placeholder = "INC-2026-0042 (optional)"
	inc.CharLimit = 128
	fi := textinput.New()
	fi.Placeholder = "agent filter…"
	fi.CharLimit = 64
	return Model{
		client:      client,
		cfg:         cfg,
		focus:       FocusLeft,
		section:     SectionWorkOrders,
		catalogTab:  CatalogSkills,
		detail:      detail.New(client, cfg.SSEEnabled),
		newGoal:     ta,
		newIncident: inc,
		filterInput: fi,
		woLoading:   true,
	}
}

func (m Model) Init() tea.Cmd {
	return tea.Batch(
		tea.WindowSize(),
		loadWorkOrders(m.client),
		loadHealth(m.client),
		loadApprovalsPanel(m.client),
		loadCatalog(m.client, ""),
		globalTick(),
	)
}

func globalTick() tea.Cmd {
	return tea.Tick(15*time.Second, func(t time.Time) tea.Msg { return tickMsg(t) })
}

func loadWorkOrders(client *api.Client) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
		defer cancel()
		items, err := client.ListWorkOrders(ctx, 50)
		return workOrdersLoadedMsg{items: items, err: err}
	}
}

func loadHealth(client *api.Client) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
		defer cancel()
		health, err := client.GetHealth(ctx)
		if err != nil {
			return healthLoadedMsg{err: err}
		}
		infra, _ := client.GetHealthInfra(ctx)
		return healthLoadedMsg{health: health, infra: infra}
	}
}

func loadApprovalsPanel(client *api.Client) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
		defer cancel()
		items, err := client.ListPendingApprovals(ctx)
		return approvalsPanelMsg{items: items, err: err}
	}
}

func loadCatalog(client *api.Client, agentFilter string) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), client.Timeout()*2)
		defer cancel()
		agents, err := client.ListCatalogAgents(ctx)
		if err != nil {
			return catalogLoadedMsg{err: err}
		}
		tools, _ := client.ListCatalogTools(ctx)
		skills, _ := client.ListCatalogSkills(ctx)
		plans, _ := client.ListCatalogPlans(ctx)
		memory, _ := client.ListTenantMemory(ctx, agentFilter, 200)
		return catalogLoadedMsg{agents: agents, tools: tools, skills: skills, plans: plans, memory: memory}
	}
}

func createWorkOrder(client *api.Client, goal, incidentID string) tea.Cmd {
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

func findWorkOrderForJob(client *api.Client, jobID string, orders []api.InvestigationSummary) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), client.Timeout()*2)
		defer cancel()
		for _, wo := range orders {
			jobs, err := client.GetInvestigationJobs(ctx, wo.InvestigationID)
			if err != nil {
				continue
			}
			for _, j := range jobs {
				if j.JobID == jobID {
					return openWOMsg{id: wo.InvestigationID}
				}
			}
		}
		return openWOMsg{err: fmt.Errorf("no work order for job %s", jobID)}
	}
}

func (m Model) InputActive() bool {
	if m.overlayOpen {
		return true
	}
	if m.filtering {
		return true
	}
	return m.detail.InputActive()
}

func (m Model) Update(msg tea.Msg) (Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		pl := layout.OperatorConsolePaneLayout(msg.Width, msg.Height, layout.DefaultLeftPanelRatio)
		innerW, innerH := pl.RightInnerSize()
		m.detail.SetSize(max(10, innerW), max(4, innerH))
		leftW, _ := pl.LeftInnerSize()
		m.newGoal.SetWidth(max(40, leftW-4))
		m.filterInput.Width = max(20, leftW-4)
		var dcmd tea.Cmd
		m.detail, dcmd = m.detail.Update(msg)
		return m, dcmd

	case workOrdersLoadedMsg:
		m.woLoading = false
		if msg.err != nil {
			m.woErr = msg.err.Error()
			return m, nil
		}
		m.woErr = ""
		m.workOrders = msg.items
		m.woCursor = clampCursor(m.woCursor, len(m.workOrders))
		return m, nil

	case healthLoadedMsg:
		if msg.err == nil {
			m.health = msg.health
			m.infra = msg.infra
		}
		return m, nil

	case approvalsPanelMsg:
		if msg.err == nil {
			m.approvals = msg.items
			m.approvalCursor = clampCursor(m.approvalCursor, len(m.approvals))
		}
		return m, nil

	case catalogLoadedMsg:
		m.catalogLoading = false
		if msg.err != nil {
			m.catalogErr = msg.err.Error()
			return m, nil
		}
		m.catalogErr = ""
		m.catalogAgents = msg.agents
		m.catalogTools = msg.tools
		m.catalogSkills = msg.skills
		m.catalogPlans = msg.plans
		m.catalogMemory = msg.memory
		m.catalogCursor = clampCursor(m.catalogCursor, m.catalogItemCount())
		return m, nil

	case catalogDetailLoadedMsg:
		if msg.err != nil {
			m.focus = FocusRight
			text := msg.err.Error()
			if msg.mode != detail.CatalogNone {
				text = "Catalog: " + text
			}
			m.detail.ShowCatalogDetail(msg.mode, style.ErrorStyle().Render(text))
			return m, nil
		}
		m.focus = FocusRight
		m.detail.ShowCatalogDetail(msg.mode, msg.text)
		return m, nil

	case engagementCreatedMsg:
		m.creating = false
		m.overlayOpen = false
		if msg.err != nil {
			m.woErr = msg.err.Error()
			return m, nil
		}
		m.selectedWO = msg.id
		m.focus = FocusRight
		return m, tea.Batch(loadWorkOrders(m.client), m.detail.Load(msg.id))

	case openWOMsg:
		if msg.err != nil {
			m.err = msg.err.Error()
			return m, nil
		}
		m.selectedWO = msg.id
		m.focus = FocusRight
		m.detail.ClearCatalogDetail()
		return m, m.detail.Load(msg.id)

	case approvalActionMsg:
		m.confirmAction = ""
		if msg.err != nil {
			m.err = msg.err.Error()
		}
		return m, loadApprovalsPanel(m.client)

	case tickMsg:
		return m, tea.Batch(globalTick(), loadApprovalsPanel(m.client))

	case tea.KeyMsg:
		if m.overlayOpen {
			return m.handleOverlayKey(msg)
		}
		if m.filtering {
			return m.handleFilterKey(msg)
		}
		if m.confirmAction != "" && m.focus == FocusLeft && m.section == SectionApprovals {
			return m.handleApprovalConfirm(msg)
		}
		return m.handleKey(msg)

	default:
		if m.overlayOpen || m.filtering {
			return m, nil
		}
		var dcmd tea.Cmd
		m.detail, dcmd = m.detail.Update(msg)
		return m, dcmd
	}

	return m, nil
}

func (m Model) handleKey(msg tea.KeyMsg) (Model, tea.Cmd) {
	if m.detail.InputActive() && m.focus == FocusRight {
		var dcmd tea.Cmd
		m.detail, dcmd = m.detail.Update(msg)
		return m, dcmd
	}

	switch msg.String() {
	case "tab":
		m.focus = ToggleFocus(m.focus)
		if m.focus == FocusRight && m.selectedWO != "" {
			return m, nil
		}
		return m, nil
	case "esc":
		if m.focus == FocusRight {
			if m.detail.CatalogModeActive() {
				m.detail.ClearCatalogDetail()
			}
			m.focus = FocusLeft
			return m, nil
		}
	case "1", "2", "3", "4", "5":
		if sec, ok := SectionFromKey(msg.String()); ok {
			m.section = sec
			if sec == SectionCatalog {
				m.catalogCursor = 0
			}
			return m, nil
		}
	case "[", "{":
		if m.focus == FocusLeft {
			m.section = PrevSection(m.section)
			return m, nil
		}
	case "]", "}":
		if m.focus == FocusLeft {
			m.section = NextSection(m.section)
			return m, nil
		}
	case "r":
		if m.focus == FocusLeft {
			switch m.section {
			case SectionWorkOrders:
				m.woLoading = true
				return m, loadWorkOrders(m.client)
			case SectionStatus:
				return m, loadHealth(m.client)
			case SectionApprovals:
				return m, loadApprovalsPanel(m.client)
			case SectionCatalog:
				m.catalogLoading = true
				return m, loadCatalog(m.client, m.memoryFilter)
			}
		}
	}

	if m.focus == FocusRight {
		var dcmd tea.Cmd
		m.detail, dcmd = m.detail.Update(msg)
		return m, dcmd
	}

	// Left panel keys
	switch msg.String() {
	case "up", "k":
		m.moveLeftCursor(-1)
	case "down", "j":
		m.moveLeftCursor(1)
	case "pgup", "u":
		m.moveLeftCursor(-m.leftPageSize())
	case "pgdown", "d":
		m.moveLeftCursor(m.leftPageSize())
	case "g":
		m.jumpLeftTop()
	case "G":
		m.jumpLeftBottom()
	case "left", "h":
		if m.section == SectionCatalog {
			m.catalogTab = CatalogTab(int(m.catalogTab)-1+int(catalogTabCount)) % catalogTabCount
			m.catalogCursor = 0
		} else if m.focus == FocusLeft {
			m.section = PrevSection(m.section)
		}
	case "right", "l":
		if m.section == SectionCatalog {
			m.catalogTab = CatalogTab((int(m.catalogTab) + 1) % int(catalogTabCount))
			m.catalogCursor = 0
		} else if m.focus == FocusLeft {
			m.section = NextSection(m.section)
		}
	case "a":
		if m.section == SectionApprovals && len(m.approvals) > 0 {
			m.confirmAction = "approve"
		} else if m.section == SectionCatalog {
			m.catalogTab = CatalogAgents
			m.catalogCursor = 0
		}
	case "t":
		if m.section == SectionCatalog {
			m.catalogTab = CatalogTools
			m.catalogCursor = 0
		}
	case "s":
		if m.section == SectionCatalog {
			m.catalogTab = CatalogSkills
			m.catalogCursor = 0
		}
	case "p":
		if m.section == SectionCatalog {
			m.catalogTab = CatalogPlans
			m.catalogCursor = 0
		}
	case "m":
		if m.section == SectionCatalog {
			m.catalogTab = CatalogMemory
			m.catalogCursor = 0
		}
	case "/":
		if m.section == SectionCatalog && m.catalogTab == CatalogMemory {
			m.filtering = true
			m.filterInput.Focus()
			m.filterInput.SetValue(m.memoryFilter)
		}
	case "n":
		if m.section == SectionWorkOrders {
			m.overlayOpen = true
			m.newGoal.SetValue("")
			m.newIncident.SetValue("")
			m.newGoal.Focus()
		}
	case "enter":
		return m.handleEnter()
	case "x":
		if m.section == SectionApprovals && len(m.approvals) > 0 {
			m.confirmAction = "reject"
		}
	}

	return m, nil
}

func (m Model) handleEnter() (Model, tea.Cmd) {
	switch m.section {
	case SectionWorkOrders:
		if len(m.workOrders) == 0 {
			return m, nil
		}
		wo := m.workOrders[m.woCursor]
		m.selectedWO = wo.InvestigationID
		m.focus = FocusRight
		m.detail.ClearCatalogDetail()
		return m, m.detail.Load(wo.InvestigationID)
	case SectionApprovals:
		if len(m.approvals) == 0 {
			return m, nil
		}
		a := m.approvals[m.approvalCursor]
		return m, findWorkOrderForJob(m.client, a.JobID, m.workOrders)
	case SectionCatalog:
		return m.openCatalogDetail()
	}
	return m, nil
}

func (m Model) openCatalogDetail() (Model, tea.Cmd) {
	items := m.catalogItemCount()
	if items == 0 {
		return m, nil
	}
	idx := m.catalogCursor
	switch m.catalogTab {
	case CatalogAgents:
		if idx >= len(m.catalogAgents) {
			return m, nil
		}
		name := m.catalogAgents[idx].Name
		return m, loadCatalogAgent(m.client, name)
	case CatalogSkills:
		if idx >= len(m.catalogSkills) {
			return m, nil
		}
		id := m.catalogSkills[idx].CatalogSkillID()
		if id == "" {
			return m, nil
		}
		return m, loadCatalogSkill(m.client, id)
	case CatalogTools:
		if idx >= len(m.catalogTools) {
			return m, nil
		}
		t := m.catalogTools[idx]
		w := m.width / 2
		return m, func() tea.Msg {
			return catalogDetailLoadedMsg{mode: detail.CatalogTool, text: detail.FormatCatalogTool(&t, w)}
		}
	case CatalogPlans:
		if idx >= len(m.catalogPlans) {
			return m, nil
		}
		p := m.catalogPlans[idx]
		w := m.width / 2
		return m, func() tea.Msg {
			return catalogDetailLoadedMsg{mode: detail.CatalogPlan, text: detail.FormatCatalogPlan(&p, w)}
		}
	case CatalogMemory:
		if idx >= len(m.catalogMemory) {
			return m, nil
		}
		e := m.catalogMemory[idx]
		w := m.width / 2
		return m, func() tea.Msg {
			return catalogDetailLoadedMsg{mode: detail.CatalogMemory, text: detail.FormatCatalogMemory(&e, w)}
		}
	}
	return m, nil
}

func loadCatalogAgent(client *api.Client, name string) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
		defer cancel()
		agent, err := client.GetCatalogAgent(ctx, name)
		if err != nil {
			return catalogDetailLoadedMsg{mode: detail.CatalogAgent, err: err}
		}
		return catalogDetailLoadedMsg{mode: detail.CatalogAgent, text: detail.FormatCatalogAgent(agent, 72)}
	}
}

func loadCatalogSkill(client *api.Client, skillID string) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
		defer cancel()
		skill, err := client.GetCatalogSkill(ctx, skillID)
		if err != nil {
			return catalogDetailLoadedMsg{mode: detail.CatalogSkill, err: err}
		}
		return catalogDetailLoadedMsg{mode: detail.CatalogSkill, text: detail.FormatCatalogSkill(skill, 72)}
	}
}

func (m Model) handleOverlayKey(msg tea.KeyMsg) (Model, tea.Cmd) {
	switch msg.String() {
	case "esc":
		m.overlayOpen = false
		m.newGoal.Blur()
		return m, nil
	case "ctrl+s", "ctrl+enter":
		goal := strings.TrimSpace(m.newGoal.Value())
		incident := strings.TrimSpace(m.newIncident.Value())
		if goal == "" && incident == "" {
			return m, nil
		}
		m.creating = true
		m.overlayOpen = false
		return m, createWorkOrder(m.client, goal, incident)
	}
	var cmd tea.Cmd
	m.newGoal, cmd = m.newGoal.Update(msg)
	var incCmd tea.Cmd
	m.newIncident, incCmd = m.newIncident.Update(msg)
	return m, tea.Batch(cmd, incCmd)
}

func (m Model) handleFilterKey(msg tea.KeyMsg) (Model, tea.Cmd) {
	switch msg.String() {
	case "esc", "enter":
		m.filtering = false
		m.filterInput.Blur()
		m.memoryFilter = strings.TrimSpace(m.filterInput.Value())
		m.catalogLoading = true
		return m, loadCatalog(m.client, m.memoryFilter)
	}
	var cmd tea.Cmd
	m.filterInput, cmd = m.filterInput.Update(msg)
	return m, cmd
}

func (m Model) handleApprovalConfirm(msg tea.KeyMsg) (Model, tea.Cmd) {
	switch msg.String() {
	case "y":
		if len(m.approvals) == 0 {
			m.confirmAction = ""
			return m, nil
		}
		a := m.approvals[m.approvalCursor]
		decision := m.confirmAction
		client := m.client
		return m, func() tea.Msg {
			ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
			defer cancel()
			err := client.ResumeJob(ctx, a.JobID, decision, a.ApprovalID)
			return approvalActionMsg{err: err}
		}
	case "n", "esc":
		m.confirmAction = ""
	}
	return m, nil
}

func (m *Model) moveLeftCursor(delta int) {
	switch m.section {
	case SectionWorkOrders:
		m.woCursor += delta
		m.woCursor = clampCursor(m.woCursor, len(m.workOrders))
	case SectionApprovals:
		m.approvalCursor += delta
		m.approvalCursor = clampCursor(m.approvalCursor, len(m.approvals))
	case SectionCatalog:
		m.catalogCursor += delta
		m.catalogCursor = clampCursor(m.catalogCursor, m.catalogItemCount())
	}
}

func (m *Model) jumpLeftTop() {
	switch m.section {
	case SectionWorkOrders:
		m.woCursor = 0
	case SectionApprovals:
		m.approvalCursor = 0
	case SectionCatalog:
		m.catalogCursor = 0
	}
}

func (m *Model) jumpLeftBottom() {
	switch m.section {
	case SectionWorkOrders:
		if len(m.workOrders) > 0 {
			m.woCursor = len(m.workOrders) - 1
		}
	case SectionApprovals:
		if len(m.approvals) > 0 {
			m.approvalCursor = len(m.approvals) - 1
		}
	case SectionCatalog:
		if n := m.catalogItemCount(); n > 0 {
			m.catalogCursor = n - 1
		}
	}
}

func (m Model) catalogItemCount() int {
	switch m.catalogTab {
	case CatalogAgents:
		return len(m.catalogAgents)
	case CatalogTools:
		return len(m.catalogTools)
	case CatalogSkills:
		return len(m.catalogSkills)
	case CatalogPlans:
		return len(m.catalogPlans)
	case CatalogMemory:
		return len(m.catalogMemory)
	}
	return 0
}

func (m Model) leftPageSize() int {
	if m.width <= 0 || m.height <= 0 {
		return 10
	}
	left, _, _ := layout.OperatorConsoleLayout(m.width, m.height, layout.DefaultLeftPanelRatio)
	showQueues := left.Width >= 72
	innerW := max(10, left.Width)
	heights := sectionHeights(left.Height, m.section, showQueues)
	h := heights[m.section]
	sec := panels.Section{Height: h, Width: innerW, Active: true}
	return sec.VisibleLines()
}

func (m Model) View() string {
	if m.width <= 0 {
		m.width = 80
	}
	if m.height <= 0 {
		m.height = 24
	}
	pl := layout.OperatorConsolePaneLayout(m.width, m.height, layout.DefaultLeftPanelRatio)

	if pl.Mode == layout.ModeLimit {
		msg := style.HelpStyle().Render("Terminal too small (need 10×9). Resize to continue.")
		return fit.ComposeFrame(m.width, m.height, fit.FitBlock(m.width, m.height, msg))
	}

	leftW, bodyH := pl.LeftInnerSize()
	rightW, _ := pl.RightInnerSize()
	sepW := max(1, pl.Separator.Width)
	if pl.Mode == layout.ModePortrait {
		sepW = 0
	}

	leftInner := fit.FitBlock(leftW, bodyH, m.renderLeft(leftW, bodyH))
	rightInner := m.detail.View()

	sepBorder := style.SectionFrameStyle(m.focus == FocusLeft)
	rightBorder := style.SectionFrameStyle(m.focus == FocusRight)

	var body string
	switch pl.Mode {
	case layout.ModePortrait:
		body = fit.JoinPortraitPanes(m.width, pl.Left.Height, pl.Right.Height, leftInner, rightInner, rightBorder)
	default:
		body = fit.JoinOperatorPanes(leftW, sepW, rightW, bodyH, leftInner, rightInner, sepBorder, rightBorder)
	}

	keybar := RenderKeybar(m.focus, m.section, m.detail.CurrentTab(), m.cfg.APIURL, m.cfg.TenantID, m.width, m.overlayOpen, m.InputActive())
	footerLine := fit.PadLine(pl.Footer.Width, keybar)

	out := body + "\n" + footerLine
	if m.overlayOpen {
		out = components.RenderOverlayOn(body, m.renderOverlay(), m.width, bodyH) + "\n" + footerLine
	}
	return fit.ComposeFrame(m.width, m.height, out)
}

func (m Model) renderLeft(w, h int) string {
	if w <= 0 {
		w = 40
	}
	showQueues := w >= 72
	sections := visibleLeftSections(showQueues)
	minNeeded := (len(sections)-1)*collapsedSectionHeight + 5
	if h < minNeeded {
		focused := m.focus == FocusLeft
		return m.buildSection(m.section, w, h, focused, true)
	}

	heights := sectionHeights(h, m.section, showQueues)

	var parts []string
	for _, sec := range sections {
		sh := heights[sec]
		if sh < 1 {
			sh = 1
		}
		active := m.section == sec
		focused := m.focus == FocusLeft && active
		parts = append(parts, m.buildSection(sec, w, sh, focused, active))
	}
	return fit.FitBlock(w, h, strings.Join(parts, "\n"))
}

func (m Model) buildSection(sec LeftSection, w, sectionH int, focused, active bool) string {
	switch sec {
	case SectionStatus:
		return m.statusSection(w, sectionH, focused, active)
	case SectionApprovals:
		return m.approvalsSection(w, sectionH, focused, active)
	case SectionQueues:
		return m.queuesSection(w, sectionH, focused, active)
	case SectionCatalog:
		return m.catalogSection(w, sectionH, focused, active)
	case SectionWorkOrders:
		return m.workOrdersSection(w, sectionH, focused, active)
	}
	return ""
}

func (m Model) statusSection(w, h int, focused, active bool) string {
	var lines []string
	apiOK := "○"
	if m.health != nil && m.health.Status == "ok" {
		apiOK = style.SuccessStyle().Render("● ok")
	}
	stream := "○ poll"
	if m.detail.StreamLive() {
		stream = style.SuccessStyle().Render("● live")
	}
	lines = append(lines, fmt.Sprintf("API %s  %s", apiOK, stream))
	lines = append(lines, fmt.Sprintf("tenant: %s", m.cfg.TenantID))
	if m.infra != nil && m.infra.WorkersHint != "" {
		lines = append(lines, style.HelpStyle().Render(fit.Plain(max(8, w-4), m.infra.WorkersHint)))
	}
	summary := ""
	if !active {
		if m.health != nil && m.health.Status == "ok" {
			summary = "api ok"
		} else {
			summary = "api down"
		}
	}
	return panels.Section{
		Key: SectionStatus.KeyHint(), Name: "Status", Items: lines,
		Height: h, Width: w, Focused: focused, Active: active, Collapsed: !active,
		CollapsedSummary: summary,
	}.View()
}

func (m Model) workOrdersSection(w, h int, focused, active bool) string {
	var items []string
	if m.woLoading {
		items = []string{style.HelpStyle().Render("Loading…")}
	} else if m.woErr != "" {
		items = []string{style.ErrorStyle().Render(m.woErr)}
	} else if len(m.workOrders) == 0 {
		items = []string{style.HelpStyle().Render("No work orders — n new")}
	} else {
		lineW := max(10, w-4)
		for _, wo := range m.workOrders {
			items = append(items, presentation.WorkOrderListLine(wo, lineW))
		}
	}
	summary := ""
	if !active {
		summary = fmt.Sprintf("%d orders", len(m.workOrders))
	}
	sec := panels.Section{
		Key: SectionWorkOrders.KeyHint(), Name: "Work orders", Items: items,
		Cursor: m.woCursor, Height: h, Width: w, Focused: focused,
		Active: active, Collapsed: !active, CollapsedSummary: summary,
	}
	return sec.View()
}

func (m Model) approvalsSection(w, h int, focused, active bool) string {
	var items []string
	if len(m.approvals) == 0 {
		items = []string{style.HelpStyle().Render("No pending approvals")}
	} else {
		limit := len(m.approvals)
		if limit > 5 {
			limit = 5
		}
		rows := [][]string{presentation.ApprovalHeader()}
		for i := 0; i < limit; i++ {
			rows = append(rows, presentation.ApprovalCells(m.approvals[i]))
		}
		table := presentation.RenderTable(rows)
		items = strings.Split(table, "\n")
		if len(items) > 1 {
			items = items[1:]
		}
	}
	summary := ""
	if !active {
		summary = fmt.Sprintf("%d pending", len(m.approvals))
	}
	sec := panels.Section{
		Key: SectionApprovals.KeyHint(), Name: "Approvals", Items: items,
		Cursor: m.approvalCursor, Height: h, Width: w, Focused: focused,
		Active: active, Collapsed: !active, Badge: len(m.approvals), CollapsedSummary: summary,
	}
	if m.confirmAction != "" && focused && active {
		sec.Extra = style.ErrorStyle().Render(fmt.Sprintf("Confirm %s? y/n", m.confirmAction))
	}
	return sec.View()
}

func (m Model) queuesSection(w, h int, focused, active bool) string {
	counts := map[string]int{}
	for _, wo := range m.workOrders {
		counts[wo.Status]++
	}
	lines := []string{
		fmt.Sprintf("open         %d", counts["open"]),
		fmt.Sprintf("in_progress  %d", counts["in_progress"]+counts["running"]),
		fmt.Sprintf("completed    %d", counts["completed"]+counts["closed"]),
		fmt.Sprintf("failed       %d", counts["failed"]),
		fmt.Sprintf("pending_hitl %d", len(m.approvals)),
	}
	summary := fmt.Sprintf("open=%d run=%d done=%d",
		counts["open"], counts["in_progress"]+counts["running"], counts["completed"]+counts["closed"])
	return panels.Section{
		Key: SectionQueues.KeyHint(), Name: "Queues", Items: lines,
		Height: h, Width: w, Focused: focused, Active: active, Collapsed: !active,
		CollapsedSummary: summary,
	}.View()
}

func (m Model) catalogSection(w, h int, focused, active bool) string {
	var header []string
	var items []string
	summary := m.catalogTab.Label()
	if !active {
		summary += fmt.Sprintf(" (%d)", m.catalogItemCount())
	} else {
		header = append(header, components.RenderTabs(catalogTabLabels(), int(m.catalogTab), max(8, w-4)))
		if focused {
			hint := "a agents · s skills · m memory · t tools · p plans"
			if w < 50 {
				hint = "[a/s/m/t/p] tabs"
			}
			header = append(header, style.HelpStyle().Render(fit.Plain(max(8, w-4), hint)))
		}
		if m.catalogLoading {
			items = []string{style.HelpStyle().Render("Loading…")}
		} else if m.catalogErr != "" {
			items = []string{style.ErrorStyle().Render(m.catalogErr)}
		} else {
			items = m.catalogListLines(max(8, w-4))
		}
	}
	return panels.Section{
		Key: SectionCatalog.KeyHint(), Name: "Catalog", Items: items,
		HeaderLines: header, Cursor: m.catalogCursor, Height: h, Width: w, Focused: focused,
		Active: active, Collapsed: !active, CollapsedSummary: summary,
	}.View()
}

func (m Model) catalogListLines(width int) []string {
	var lines []string
	switch m.catalogTab {
	case CatalogAgents:
		for _, a := range m.catalogAgents {
			lines = append(lines, presentation.FormatPair(a.Name, a.Role, width))
		}
	case CatalogSkills:
		for _, s := range m.catalogSkills {
			lines = append(lines, presentation.FormatPair(s.Name, s.CatalogSkillID(), width))
		}
	case CatalogMemory:
		for _, e := range m.catalogMemory {
			lines = append(lines, presentation.FormatPair(e.SourceAgent, e.Content, width))
		}
	case CatalogTools:
		for _, t := range m.catalogTools {
			label := t.Name
			if label == "" {
				label = t.CatalogToolID()
			}
			lines = append(lines, presentation.FormatPair(label, t.RiskTier, width))
		}
	case CatalogPlans:
		for _, p := range m.catalogPlans {
			lines = append(lines, presentation.FormatPair(p.Name, p.CatalogPlanID(), width))
		}
	}
	if len(lines) == 0 {
		return []string{style.HelpStyle().Render("(empty — press a/s/m/t/p)")}
	}
	return lines
}

func (m Model) renderRight(w, h int) string {
	return m.detail.View()
}

func (m Model) renderOverlay() string {
	return "New work order\n\n" +
		"Incident ID (optional):\n" + m.newIncident.View() + "\n\n" +
		"Goal:\n" + m.newGoal.View() + "\n\n" +
		style.HelpStyle().Render("Ctrl+Enter submit · Esc cancel")
}

func clampCursor(cur, n int) int {
	if n == 0 {
		return 0
	}
	if cur < 0 {
		return 0
	}
	if cur >= n {
		return n - 1
	}
	return cur
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
