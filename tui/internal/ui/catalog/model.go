package catalog

import (
	"context"
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/table"
	"github.com/charmbracelet/bubbles/textinput"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"

	"github.com/butbeautifulv/egregore/tui/internal/api"
	"github.com/butbeautifulv/egregore/tui/internal/jsonfmt"
	"github.com/butbeautifulv/egregore/tui/internal/style"
	"github.com/butbeautifulv/egregore/tui/internal/textutil"
	"github.com/butbeautifulv/egregore/tui/internal/ui/fit"
	"github.com/butbeautifulv/egregore/tui/internal/ui/tableutil"
)

type Tab int

const (
	TabAgents Tab = iota
	TabTools
	TabSkills
	TabPlans
	TabMemory
)

type ViewMode int

const (
	ViewList ViewMode = iota
	ViewAgentDetail
	ViewSkillDetail
	ViewToolDetail
	ViewPlanDetail
	ViewMemoryDetail
)

type loadedMsg struct {
	agents []api.CatalogAgent
	tools  []api.CatalogTool
	skills []api.CatalogSkill
	plans  []api.CatalogPlan
	memory []api.MemoryEntry
	err    error
}

type agentDetailMsg struct {
	agent *api.CatalogAgentDetail
	err   error
}

type skillDetailMsg struct {
	skill *api.CatalogSkill
	err   error
}

// Model is the catalog browser.
type Model struct {
	client       *api.Client
	width        int
	height       int
	tab          Tab
	viewMode     ViewMode
	table        table.Model
	search       textinput.Model
	filtering    bool
	agents       []api.CatalogAgent
	tools        []api.CatalogTool
	skills       []api.CatalogSkill
	plans        []api.CatalogPlan
	memory       []api.MemoryEntry
	memoryFilter string
	agentDetail  *api.CatalogAgentDetail
	skillDetail  *api.CatalogSkill
	toolDetail   *api.CatalogTool
	planDetail   *api.CatalogPlan
	memoryDetail *api.MemoryEntry
	detailVP     viewport.Model
	err          string
	loading      bool
	detailLoading bool
}

var agentsColSpecs = []tableutil.ColumnSpec{
	{Title: "Agent", MinWidth: 10, Weight: 2},
	{Title: "Role", MinWidth: 8, Weight: 1},
	{Title: "Meta", MinWidth: 8, Weight: 0},
}

var toolsColSpecs = []tableutil.ColumnSpec{
	{Title: "Tool", MinWidth: 10, Weight: 1},
	{Title: "Description", MinWidth: 12, Weight: 3},
	{Title: "Risk", MinWidth: 6, Weight: 0},
}

var skillsColSpecs = []tableutil.ColumnSpec{
	{Title: "Skill", MinWidth: 10, Weight: 1},
	{Title: "Name", MinWidth: 10, Weight: 2},
	{Title: "Approval", MinWidth: 8, Weight: 0},
}

var plansColSpecs = []tableutil.ColumnSpec{
	{Title: "Plan", MinWidth: 10, Weight: 1},
	{Title: "Personas", MinWidth: 12, Weight: 3},
	{Title: "Active", MinWidth: 6, Weight: 0},
}

var memoryColSpecs = []tableutil.ColumnSpec{
	{Title: "ID", MinWidth: 10, Weight: 1},
	{Title: "Content", MinWidth: 12, Weight: 3},
	{Title: "Meta", MinWidth: 8, Weight: 1},
}

func New(client *api.Client) Model {
	t := table.New(
		table.WithFocused(true),
		table.WithHeight(12),
	)
	t.SetStyles(tableutil.CompactStyles())

	si := textinput.New()
	si.Placeholder = "agent filter…"
	si.CharLimit = 64

	vp := viewport.New(80, 20)

	return Model{
		client:   client,
		table:    t,
		search:   si,
		detailVP: vp,
		loading:  true,
	}
}

func (m Model) Init() tea.Cmd {
	return loadAll(m.client, "")
}

func loadAll(client *api.Client, agentFilter string) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), client.Timeout()*2)
		defer cancel()
		agents, err := client.ListCatalogAgents(ctx)
		if err != nil {
			return loadedMsg{err: err}
		}
		tools, _ := client.ListCatalogTools(ctx)
		skills, _ := client.ListCatalogSkills(ctx)
		plans, _ := client.ListCatalogPlans(ctx)
		memory, _ := client.ListTenantMemory(ctx, agentFilter, 200)
		return loadedMsg{agents: agents, tools: tools, skills: skills, plans: plans, memory: memory}
	}
}

func loadAgent(client *api.Client, name string) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
		defer cancel()
		agent, err := client.GetCatalogAgent(ctx, name)
		return agentDetailMsg{agent: agent, err: err}
	}
}

func loadSkill(client *api.Client, skillID string) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), client.Timeout())
		defer cancel()
		skill, err := client.GetCatalogSkill(ctx, skillID)
		return skillDetailMsg{skill: skill, err: err}
	}
}

func (m Model) Update(msg tea.Msg) (Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		m.applyLayout()
		m.detailVP.Width = max(20, msg.Width-4)
		m.detailVP.Height = max(10, msg.Height-10)
		m.search.Width = max(20, msg.Width-6)
		m.rerenderDetail()
		return m, nil

	case loadedMsg:
		m.loading = false
		if msg.err != nil {
			m.err = msg.err.Error()
			return m, nil
		}
		m.err = ""
		m.agents = msg.agents
		m.tools = msg.tools
		m.skills = msg.skills
		m.plans = msg.plans
		m.memory = msg.memory
		if m.width > 0 {
			m.applyLayout()
		} else {
			m.rebuildTable()
		}
		return m, nil

	case agentDetailMsg:
		m.detailLoading = false
		if msg.err != nil {
			m.err = msg.err.Error()
			return m, nil
		}
		m.err = ""
		m.agentDetail = msg.agent
		m.viewMode = ViewAgentDetail
		m.renderAgentDetail()
		return m, nil

	case skillDetailMsg:
		m.detailLoading = false
		if msg.err != nil {
			m.err = msg.err.Error()
			return m, nil
		}
		m.err = ""
		m.skillDetail = msg.skill
		m.viewMode = ViewSkillDetail
		m.renderSkillDetail()
		return m, nil

	case tea.KeyMsg:
		if m.filtering {
			return m.updateFilter(msg)
		}
		if m.viewMode != ViewList {
			return m.updateDetail(msg)
		}
		return m.updateList(msg)
	}

	return m, nil
}

func (m Model) InputActive() bool {
	return m.filtering
}

func (m Model) updateList(msg tea.KeyMsg) (Model, tea.Cmd) {
	switch msg.String() {
	case "a":
		return m.switchTab(TabAgents), nil
	case "t":
		return m.switchTab(TabTools), nil
	case "s":
		return m.switchTab(TabSkills), nil
	case "p":
		return m.switchTab(TabPlans), nil
	case "m":
		return m.switchTab(TabMemory), nil
	case "left", "h":
		return m.switchTab(prevTab(m.tab)), nil
	case "right", "l":
		return m.switchTab(nextTab(m.tab)), nil
	case "/":
		if m.tab == TabMemory {
			m.filtering = true
			m.search.SetValue(m.memoryFilter)
			m.search.Focus()
			return m, textinput.Blink
		}
		return m, nil
	case "r":
		m.loading = true
		return m, loadAll(m.client, m.memoryFilter)
	case "enter":
		return m.openDetail()
	}
	var cmd tea.Cmd
	m.table, cmd = tableutil.UpdateWrap(m.table, msg, m.tabRowCount())
	return m, cmd
}

func (m Model) switchTab(tab Tab) Model {
	m.tab = tab
	m.table.SetCursor(0)
	m.applyLayout()
	return m
}

func (m Model) openDetail() (Model, tea.Cmd) {
	idx := m.table.Cursor()
	switch m.tab {
	case TabAgents:
		if idx >= 0 && idx < len(m.agents) {
			m.detailLoading = true
			m.err = ""
			return m, loadAgent(m.client, m.agents[idx].Name)
		}
	case TabSkills:
		if idx >= 0 && idx < len(m.skills) {
			skillID := m.skills[idx].SkillID
			if skillID == "" {
				skillID = m.skills[idx].Name
			}
			m.detailLoading = true
			m.err = ""
			return m, loadSkill(m.client, skillID)
		}
	case TabTools:
		if idx >= 0 && idx < len(m.tools) {
			tool := m.tools[idx]
			m.toolDetail = &tool
			m.viewMode = ViewToolDetail
			m.renderToolDetail()
		}
	case TabPlans:
		if idx >= 0 && idx < len(m.plans) {
			plan := m.plans[idx]
			m.planDetail = &plan
			m.viewMode = ViewPlanDetail
			m.renderPlanDetail()
		}
	case TabMemory:
		if idx >= 0 && idx < len(m.memory) {
			entry := m.memory[idx]
			m.memoryDetail = &entry
			m.viewMode = ViewMemoryDetail
			m.renderMemoryDetail()
		}
	}
	return m, nil
}

func (m Model) updateFilter(msg tea.KeyMsg) (Model, tea.Cmd) {
	switch msg.String() {
	case "esc":
		m.filtering = false
		m.table.Focus()
		return m, nil
	case "enter":
		m.filtering = false
		m.memoryFilter = strings.TrimSpace(m.search.Value())
		m.table.Focus()
		m.loading = true
		m.table.SetCursor(0)
		return m, loadAll(m.client, m.memoryFilter)
	}
	var cmd tea.Cmd
	m.search, cmd = m.search.Update(msg)
	return m, cmd
}

func (m Model) updateDetail(msg tea.KeyMsg) (Model, tea.Cmd) {
	switch msg.String() {
	case "esc", "backspace":
		m.viewMode = ViewList
		m.clearDetails()
		m.table.Focus()
		return m, nil
	}
	var cmd tea.Cmd
	m.detailVP, cmd = m.detailVP.Update(msg)
	return m, cmd
}

func (m *Model) clearDetails() {
	m.agentDetail = nil
	m.skillDetail = nil
	m.toolDetail = nil
	m.planDetail = nil
	m.memoryDetail = nil
}

func (m *Model) rerenderDetail() {
	switch m.viewMode {
	case ViewAgentDetail:
		m.renderAgentDetail()
	case ViewSkillDetail:
		m.renderSkillDetail()
	case ViewToolDetail:
		m.renderToolDetail()
	case ViewPlanDetail:
		m.renderPlanDetail()
	case ViewMemoryDetail:
		m.renderMemoryDetail()
	}
}

func (m *Model) colSpecsForTab() []tableutil.ColumnSpec {
	switch m.tab {
	case TabTools:
		return toolsColSpecs
	case TabSkills:
		return skillsColSpecs
	case TabPlans:
		return plansColSpecs
	case TabMemory:
		return memoryColSpecs
	default:
		return agentsColSpecs
	}
}

func (m *Model) applyLayout() {
	w := m.width
	if w <= 0 {
		w = 80
	}
	h := m.height
	tableH := 12
	if h > 0 {
		tableH = max(6, h-12)
	}
	tableutil.ApplyLayout(&m.table, w, tableH, m.colSpecsForTab())
	m.rebuildTable()
}

func (m *Model) rebuildTable() {
	switch m.tab {
	case TabAgents:
		m.setRowsAgents()
	case TabTools:
		m.setRowsTools()
	case TabSkills:
		m.setRowsSkills()
	case TabPlans:
		m.setRowsPlans()
	case TabMemory:
		m.setRowsMemory()
	}
}

func (m *Model) contentWidth() int {
	w := m.width - 4
	if w < 40 {
		return 40
	}
	return w
}

func (m *Model) setRowsAgents() {
	widths := tableutil.Widths(m.table.Columns())
	rows := make([]table.Row, 0, len(m.agents))
	for _, a := range m.agents {
		meta := agentMeta(a)
		rows = append(rows, table.Row{
			style.Truncate(a.Name, colWidth(widths, 0)),
			style.Truncate(a.Role, colWidth(widths, 1)),
			style.Truncate(meta, colWidth(widths, 2)),
		})
	}
	m.table.SetRows(rows)
}

func agentMeta(a api.CatalogAgent) string {
	enabled := "off"
	if a.Enabled {
		enabled = "on"
	}
	if a.EmpiricalTrust > 0 {
		return fmt.Sprintf("%s · %.0f%%", enabled, a.EmpiricalTrust*100)
	}
	if a.VersionTag != "" {
		return fmt.Sprintf("%s · %s", enabled, a.VersionTag)
	}
	return enabled
}

func (m *Model) setRowsTools() {
	widths := tableutil.Widths(m.table.Columns())
	rows := make([]table.Row, 0, len(m.tools))
	for _, t := range m.tools {
		name := t.Name
		if name == "" {
			name = t.ToolID
		}
		rows = append(rows, table.Row{
			style.Truncate(name, colWidth(widths, 0)),
			style.Truncate(t.Description, colWidth(widths, 1)),
			style.Truncate(t.RiskTier, colWidth(widths, 2)),
		})
	}
	m.table.SetRows(rows)
}

func (m *Model) setRowsSkills() {
	widths := tableutil.Widths(m.table.Columns())
	rows := make([]table.Row, 0, len(m.skills))
	for _, s := range m.skills {
		id := s.SkillID
		if id == "" {
			id = s.Name
		}
		name := s.Name
		if name == "" {
			name = "—"
		}
		rows = append(rows, table.Row{
			style.Truncate(id, colWidth(widths, 0)),
			style.Truncate(name, colWidth(widths, 1)),
			style.Truncate(s.ApprovalStatus, colWidth(widths, 2)),
		})
	}
	m.table.SetRows(rows)
}

func (m *Model) setRowsPlans() {
	widths := tableutil.Widths(m.table.Columns())
	rows := make([]table.Row, 0, len(m.plans))
	for _, p := range m.plans {
		name := p.Name
		if name == "" {
			name = p.PlanID
		}
		active := "no"
		if p.Active {
			active = "yes"
		}
		rows = append(rows, table.Row{
			style.Truncate(name, colWidth(widths, 0)),
			style.Truncate(strings.Join(p.Personas, " → "), colWidth(widths, 1)),
			style.Truncate(active, colWidth(widths, 2)),
		})
	}
	m.table.SetRows(rows)
}

func (m *Model) setRowsMemory() {
	widths := tableutil.Widths(m.table.Columns())
	rows := make([]table.Row, 0, len(m.memory))
	for _, e := range m.memory {
		meta := e.SourceAgent
		if e.MemoryType != "" {
			if meta != "" {
				meta += " · "
			}
			meta += e.MemoryType
		}
		rows = append(rows, table.Row{
			style.Truncate(e.ID, colWidth(widths, 0)),
			style.Truncate(e.Content, colWidth(widths, 1)),
			style.Truncate(meta, colWidth(widths, 2)),
		})
	}
	m.table.SetRows(rows)
}

func colWidth(widths []int, idx int) int {
	if idx < len(widths) {
		return widths[idx]
	}
	return 20
}

func (m *Model) renderAgentDetail() {
	if m.agentDetail == nil {
		return
	}
	a := m.agentDetail
	w := m.contentWidth()
	var b strings.Builder
	b.WriteString(fmt.Sprintf("Role: %s\n", a.Role))
	b.WriteString(fmt.Sprintf("Enabled: %t · Trust: %.0f%% · Version: %d\n",
		a.Enabled, a.EmpiricalTrust*100, a.Version))
	if a.ProfileID != "" {
		b.WriteString("Profile: " + a.ProfileID + "\n")
	}
	if a.Description != "" {
		b.WriteString("\n" + textutil.WrapBlock(a.Description, w) + "\n")
	}
	if len(a.Tools) > 0 {
		b.WriteString("\nTools: " + strings.Join(a.Tools, ", ") + "\n")
	}
	if len(a.Skills) > 0 {
		b.WriteString("Skills: " + strings.Join(a.Skills, ", ") + "\n")
	}
	b.WriteString("\n--- System Prompt ---\n")
	b.WriteString(textutil.WrapBlock(a.SystemPrompt, w))
	m.detailVP.SetContent(b.String())
	m.detailVP.GotoTop()
}

func (m *Model) renderSkillDetail() {
	if m.skillDetail == nil {
		return
	}
	s := m.skillDetail
	w := m.contentWidth()
	var b strings.Builder
	if s.Name != "" {
		b.WriteString("Name: " + s.Name + "\n")
	}
	b.WriteString(fmt.Sprintf("ID: %s · Version: %d · Enabled: %t\n", s.SkillID, s.Version, s.Enabled))
	b.WriteString("Approval: " + s.ApprovalStatus + "\n")
	if s.Description != "" {
		b.WriteString("\n" + textutil.WrapBlock(s.Description, w) + "\n")
	}
	b.WriteString("\n--- Body ---\n")
	body := strings.TrimSpace(s.Body)
	if body == "" {
		body = "No skill body."
	}
	b.WriteString(textutil.WrapBlock(body, w))
	m.detailVP.SetContent(b.String())
	m.detailVP.GotoTop()
}

func (m *Model) renderToolDetail() {
	if m.toolDetail == nil {
		return
	}
	t := m.toolDetail
	w := m.contentWidth()
	var b strings.Builder
	b.WriteString(fmt.Sprintf("Tool ID: %s\n", t.ToolID))
	if t.Name != "" && t.Name != t.ToolID {
		b.WriteString("Name: " + t.Name + "\n")
	}
	b.WriteString(fmt.Sprintf("Risk: %s · Enabled: %t\n", t.RiskTier, t.Enabled))
	if t.Description != "" {
		b.WriteString("\n" + textutil.WrapBlock(t.Description, w))
	}
	m.detailVP.SetContent(b.String())
	m.detailVP.GotoTop()
}

func (m *Model) renderPlanDetail() {
	if m.planDetail == nil {
		return
	}
	p := m.planDetail
	w := m.contentWidth()
	var b strings.Builder
	b.WriteString(fmt.Sprintf("Plan ID: %s\n", p.PlanID))
	if p.Name != "" {
		b.WriteString("Name: " + p.Name + "\n")
	}
	b.WriteString(fmt.Sprintf("Active: %t\n", p.Active))
	if p.Description != "" {
		b.WriteString("\n" + textutil.WrapBlock(p.Description, w) + "\n")
	}
	if len(p.Personas) > 0 {
		b.WriteString("\nPersonas: " + strings.Join(p.Personas, " → ") + "\n")
	}
	m.detailVP.SetContent(b.String())
	m.detailVP.GotoTop()
}

func (m *Model) renderMemoryDetail() {
	if m.memoryDetail == nil {
		return
	}
	e := m.memoryDetail
	w := m.contentWidth()
	var b strings.Builder
	b.WriteString(fmt.Sprintf("ID: %s\nAgent: %s · Type: %s\n", e.ID, e.SourceAgent, e.MemoryType))
	b.WriteString(fmt.Sprintf("Investigation: %s\n", e.InvestigationID))
	if e.CreatedAt != "" {
		b.WriteString("Created: " + e.CreatedAt + "\n")
	}
	if e.TrustScore > 0 {
		b.WriteString(fmt.Sprintf("Trust: %.0f%%\n", e.TrustScore*100))
	}
	b.WriteString("\n")
	if trimmed := strings.TrimSpace(e.Content); trimmed != "" {
		b.WriteString(jsonfmt.FormatMessage(trimmed, w))
	}
	if e.ContentParsed != nil {
		b.WriteString("\n\n--- Parsed ---\n")
		b.WriteString(textutil.WrapBlock(jsonfmt.FormatValue(e.ContentParsed), w))
	}
	m.detailVP.SetContent(b.String())
	m.detailVP.GotoTop()
}

func (m Model) View() string {
	w := m.width
	if w <= 0 {
		w = 80
	}

	if m.viewMode != ViewList {
		return m.viewDetail(w)
	}

	var b strings.Builder
	b.WriteString(style.TitleStyle().Render("Catalog"))
	b.WriteString("\n")
	b.WriteString(m.renderTabs(w))
	b.WriteString("\n")
	if m.memoryFilter != "" && m.tab == TabMemory {
		b.WriteString(style.HelpStyle().Render(fit.Plain(w, "Filter: agent="+m.memoryFilter)))
		b.WriteString("\n")
	}
	if m.err != "" {
		b.WriteString(style.ErrorStyle().Render(fit.Plain(w, m.err)))
		b.WriteString("\n")
	}
	if m.loading || m.detailLoading {
		b.WriteString(style.HelpStyle().Render("Loading…"))
		b.WriteString("\n")
	}
	if m.filtering {
		b.WriteString(m.search.View())
		b.WriteString("\n")
	}
	if !m.loading && !m.detailLoading && m.tabRowCount() == 0 {
		b.WriteString(style.HelpStyle().Render(fit.Line(w, m.emptyTabMessage())))
		b.WriteString("\n")
	}
	if !m.detailLoading {
		b.WriteString(m.table.View())
		b.WriteString("\n")
	}
	help := "↑/↓ j/k move · enter detail · ←/→ tabs · a/t/s/p/m · r refresh"
	if m.tab == TabMemory {
		help += " · / filter"
	}
	b.WriteString(style.HelpStyle().Render(fit.Line(w, help)))
	return b.String()
}

func (m Model) viewDetail(w int) string {
	var title string
	switch m.viewMode {
	case ViewAgentDetail:
		if m.agentDetail != nil {
			title = "Agent: " + m.agentDetail.Name
		} else {
			title = "Agent"
		}
	case ViewSkillDetail:
		if m.skillDetail != nil {
			title = "Skill: " + m.skillDetail.SkillID
		} else {
			title = "Skill"
		}
	case ViewToolDetail:
		if m.toolDetail != nil {
			title = "Tool: " + m.toolDetail.ToolID
			if m.toolDetail.Name != "" {
				title = "Tool: " + m.toolDetail.Name
			}
		} else {
			title = "Tool"
		}
	case ViewPlanDetail:
		if m.planDetail != nil {
			title = "Plan: " + m.planDetail.Name
			if m.planDetail.Name == "" {
				title = "Plan: " + m.planDetail.PlanID
			}
		} else {
			title = "Plan"
		}
	case ViewMemoryDetail:
		title = "Memory"
	}
	return style.TitleStyle().Render(fit.Plain(w, title)) + "\n" +
		m.detailVP.View() + "\n" +
		style.HelpStyle().Render(fit.Line(w, "↑/↓ scroll · Esc back"))
}

func (m Model) renderTabs(w int) string {
	type tabInfo struct {
		label string
		short string
		count int
	}
	tabs := []tabInfo{
		{"Agents", "A", len(m.agents)},
		{"Tools", "T", len(m.tools)},
		{"Skills", "S", len(m.skills)},
		{"Plans", "P", len(m.plans)},
		{"Memory", "M", len(m.memory)},
	}
	useShort := w < 80
	var parts []string
	for i, info := range tabs {
		label := fmt.Sprintf("%s(%d)", info.label, info.count)
		if useShort {
			label = fmt.Sprintf("%s%d", info.short, info.count)
		}
		if Tab(i) == m.tab {
			parts = append(parts, style.NavActiveStyle().Render(label))
		} else {
			parts = append(parts, style.NavStyle().Render(label))
		}
	}
	sep := " "
	if w >= 60 {
		sep = "  "
	}
	return strings.Join(parts, sep)
}

func (m Model) tabRowCount() int {
	switch m.tab {
	case TabAgents:
		return len(m.agents)
	case TabTools:
		return len(m.tools)
	case TabSkills:
		return len(m.skills)
	case TabPlans:
		return len(m.plans)
	case TabMemory:
		return len(m.memory)
	default:
		return 0
	}
}

func (m Model) emptyTabMessage() string {
	switch m.tab {
	case TabAgents:
		return "No agents in catalog"
	case TabTools:
		return "No tools in catalog"
	case TabSkills:
		return "No skills in catalog"
	case TabPlans:
		return "No plans in catalog"
	case TabMemory:
		if m.memoryFilter != "" {
			return "No memory entries for agent " + m.memoryFilter
		}
		return "No memory entries"
	default:
		return "No data"
	}
}

func prevTab(t Tab) Tab {
	if t == TabAgents {
		return TabMemory
	}
	return t - 1
}

func nextTab(t Tab) Tab {
	if t == TabMemory {
		return TabAgents
	}
	return t + 1
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
