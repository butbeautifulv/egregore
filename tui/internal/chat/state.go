package chat

import (
	"encoding/json"
	"fmt"
	"strings"

	"github.com/butbeautifulv/egregore/tui/internal/api"
	"github.com/butbeautifulv/egregore/tui/internal/jsonfmt"
)

type ToolCall struct {
	Name          string
	Status        string // started, done, error
	ToolCallID    string
	SearchQuery   string
	ResultCount   int
	ErrorMessage  string
}

type Reasoning struct {
	CurrentSituation string
	PlanStatus       string
	ReasoningSteps   []string
	TaskCompleted    bool
}

type Entry struct {
	JobID          string
	Persona        string
	Buffer         string
	Turns          []string
	Reasoning      *Reasoning
	Tools          []ToolCall
	Streaming      bool
	AgentExpanded  bool
	JobError       string
	IsControlError bool
}

type State struct {
	entries map[string]*Entry
}

func NewState() *State {
	return &State{entries: make(map[string]*Entry)}
}

func PlannerJobID(engagementID string) string {
	return "planner:" + engagementID
}

func (s *State) Entries() []*Entry {
	out := make([]*Entry, 0, len(s.entries))
	for _, e := range s.entries {
		out = append(out, e)
	}
	return out
}

func (s *State) Get(jobID string) *Entry {
	return s.entries[jobID]
}

func (s *State) Ensure(jobID, persona string) *Entry {
	if e, ok := s.entries[jobID]; ok {
		if persona != "" && e.Persona == "" {
			e.Persona = persona
		}
		return e
	}
	e := &Entry{
		JobID:         jobID,
		Persona:       persona,
		AgentExpanded: false,
	}
	if e.Persona == "" {
		e.Persona = "agent"
	}
	s.entries[jobID] = e
	return e
}

func EventDedupeKey(event api.EngagementStreamEvent) string {
	payload := event.Payload
	if payload == nil {
		payload = map[string]interface{}{}
	}
	typ := event.Type
	switch typ {
	case "assistant_delta":
		return strings.Join([]string{typ, str(payload["job_id"]), str(payload["seq"]), str(payload["delta"])}, "|")
	case "reasoning_delta":
		steps, _ := payload["reasoning_steps"].([]interface{})
		parts := make([]string, 0, len(steps))
		for _, s := range steps {
			parts = append(parts, fmt.Sprint(s))
		}
		return strings.Join([]string{typ, str(payload["job_id"]), str(payload["plan_status"]), strings.Join(parts, ",")}, "|")
	case "assistant_snapshot":
		return strings.Join([]string{typ, str(payload["job_id"]), str(payload["text"])}, "|")
	case "tool_start", "tool_done", "tool_error":
		preview := str(payload["output_preview"])
		if len(preview) > 64 {
			preview = preview[:64]
		}
		return strings.Join([]string{typ, str(payload["job_id"]), str(payload["tool_name"]), str(payload["tool_call_id"]), preview, str(payload["error"])}, "|")
	default:
		verdict, _ := json.Marshal(payload["verdict"])
		return strings.Join([]string{typ, event.Phase, str(payload["job_id"]), str(payload["persona"]), str(payload["summary"]), string(verdict)}, "|")
	}
}

func ShouldRefreshOnEvent(event api.EngagementStreamEvent) bool {
	typ := event.Type
	phase := event.Phase
	refreshTypes := map[string]bool{
		"assistant_done": true, "job_finished": true, "job_started": true,
		"error": true, "control": true, "report": true,
	}
	if refreshTypes[typ] {
		return true
	}
	if typ == "status" && phase == "final_report" {
		return true
	}
	statusPhases := map[string]bool{
		"job_started": true, "job_finished": true, "error": true,
		"planning_done": true, "planning_error": true,
	}
	return typ == "status" && statusPhases[phase]
}

func (s *State) ApplyEvent(event api.EngagementStreamEvent, features api.APIFeatures, engagementID string) bool {
	typ := event.Type
	payload := event.Payload
	if payload == nil {
		payload = map[string]interface{}{}
	}

	controlTypes := map[string]bool{"control": true, "report": true, "control_error": true}
	jobID := str(payload["job_id"])
	persona := str(payload["persona"])

	if jobID == "" && controlTypes[typ] {
		jobID = resolveControlJobID(typ, payload, engagementID)
		if persona == "" {
			if typ == "report" {
				persona = "coordinator"
			} else {
				persona = "critic"
			}
		}
	}
	if jobID == "" {
		return false
	}

	entry := s.Ensure(jobID, persona)

	if controlTypes[typ] {
		if !shouldApplyControlEvent(typ, payload) {
			return false
		}
		entry.Buffer = controlEventText(typ, payload)
		entry.Streaming = false
		entry.IsControlError = typ == "control_error"
		return true
	}

	switch typ {
	case "reasoning_delta":
		steps := []string{}
		if raw, ok := payload["reasoning_steps"].([]interface{}); ok {
			for _, step := range raw {
				steps = append(steps, fmt.Sprint(step))
			}
		}
		entry.Reasoning = &Reasoning{
			CurrentSituation: str(payload["current_situation"]),
			PlanStatus:       str(payload["plan_status"]),
			ReasoningSteps:   steps,
			TaskCompleted:    boolVal(payload["task_completed"]),
		}
		return true
	case "assistant_delta":
		entry.Buffer += str(payload["delta"])
		entry.Streaming = true
		return true
	case "assistant_snapshot":
		text := str(payload["text"])
		if text != "" && entry.Buffer == text {
			entry.Streaming = false
			return false
		}
		if entry.Buffer == "" && text != "" {
			entry.Buffer = text
		}
		entry.Streaming = false
		return true
	case "assistant_done":
		if entry.Buffer != "" {
			entry.Turns = append(entry.Turns, entry.Buffer)
			entry.Buffer = ""
		}
		entry.Streaming = false
		return true
	case "status":
		if event.Phase == "job_finished" {
			errMsg := str(payload["error"])
			if errMsg == "" {
				errMsg = "unknown"
			}
			if payload["success"] == false {
				entry.JobError = errMsg
				if entry.Buffer == "" {
					entry.Buffer = formatJobError(errMsg)
				}
				entry.AgentExpanded = false
			} else {
				entry.JobError = ""
			}
			entry.Streaming = false
			return true
		}
	case "tool_start":
		if features.StreamAgentTools {
			toolName := str(payload["tool_name"])
			if toolName == "" {
				toolName = "tool"
			}
			label := toolName
			if skill := str(payload["skill_name"]); skill != "" {
				label = toolName + " → " + skill
			}
			tool := ToolCall{
				Name:       label,
				Status:     "started",
				ToolCallID: str(payload["tool_call_id"]),
			}
			if toolName == "playbook_search" {
				if args, ok := payload["tool_args"].(map[string]interface{}); ok {
					tool.SearchQuery = str(args["query"])
				}
			}
			entry.Tools = append(entry.Tools, tool)
			return true
		}
	case "skill_loaded":
		skill := str(payload["skill_name"])
		if skill == "" {
			skill = str(payload["skill"])
		}
		if skill == "" {
			skill = "skill"
		}
		entry.Tools = append(entry.Tools, ToolCall{Name: "load_skill → " + skill, Status: "done"})
		return true
	case "tool_done":
		if features.StreamAgentTools {
			toolCallID := str(payload["tool_call_id"])
			toolName := str(payload["tool_name"])
			if toolName == "" {
				toolName = "tool"
			}
			found := false
			for i := range entry.Tools {
				t := &entry.Tools[i]
				if t.Status == "started" && (t.ToolCallID == toolCallID || strings.HasPrefix(t.Name, toolName)) {
					if payload["ok"] == false {
						t.Status = "error"
					} else {
						t.Status = "done"
					}
					if toolName == "playbook_search" {
						if preview := str(payload["output_preview"]); preview != "" {
							t.ResultCount = parsePlaybookSearchCount(preview)
						}
					}
					found = true
					break
				}
			}
			if !found {
				status := "done"
				if payload["ok"] == false {
					status = "error"
				}
				entry.Tools = append(entry.Tools, ToolCall{Name: toolName, Status: status})
			}
			return true
		}
	case "tool_error":
		if features.StreamAgentTools {
			toolCallID := str(payload["tool_call_id"])
			toolName := str(payload["tool_name"])
			if toolName == "" {
				toolName = "tool"
			}
			errMsg := str(payload["error"])
			found := false
			for i := range entry.Tools {
				t := &entry.Tools[i]
				if t.Status == "started" && (t.ToolCallID == toolCallID || strings.HasPrefix(t.Name, toolName)) {
					t.Status = "error"
					t.ErrorMessage = errMsg
					found = true
					break
				}
			}
			if !found {
				entry.Tools = append(entry.Tools, ToolCall{
					Name:         toolName,
					Status:       "error",
					ToolCallID:   toolCallID,
					ErrorMessage: errMsg,
				})
			}
			return true
		}
	}
	return false
}

func (s *State) HydrateFromDetail(detail *api.InvestigationDetail, engagementID string) {
	if detail == nil {
		return
	}
	for _, item := range detail.FindingsSummary {
		jobID := str(item["job_id"])
		if jobID == "" {
			continue
		}
		entry := s.Ensure(jobID, str(item["persona"]))
		if entry.Buffer == "" {
			if finding, ok := item["finding"]; ok {
				entry.Buffer = formatFindingText(finding)
			} else {
				entry.Buffer = formatFindingText(item)
			}
		}
	}

	plannerID := PlannerJobID(engagementID)
	planner := s.Ensure(plannerID, "planner")
	if planner.Buffer == "" && (len(detail.PlannerPlan) > 0 || detail.PlannerRationale != "") {
		planner.Buffer = jsonfmt.FormatPlannerFromDetail(
			detail.PlannerPlan,
			detail.PlannerRationale,
			detail.PlannerSubGoals,
			detail.PlannerDependsOn,
			detail.ExecutionMode,
			detail.SynthesisPersona,
		)
	}
}

func SortEntries(entries []*Entry, plannerID string, plannerPlan []string, jobs []api.JobSummary) []*Entry {
	order := []string{plannerID}
	for _, persona := range plannerPlan {
		for _, job := range jobs {
			if job.Persona == persona {
				order = append(order, job.JobID)
				break
			}
		}
	}
	for _, job := range jobs {
		if !contains(order, job.JobID) {
			order = append(order, job.JobID)
		}
	}
	rank := make(map[string]int, len(order))
	for i, id := range order {
		rank[id] = i
	}
	sorted := make([]*Entry, len(entries))
	copy(sorted, entries)
	for i := 0; i < len(sorted)-1; i++ {
		for j := i + 1; j < len(sorted); j++ {
			ri, rj := rank[sorted[i].JobID], rank[sorted[j].JobID]
			if ri == 0 && sorted[i].JobID != plannerID {
				ri = 999
			}
			if rj == 0 && sorted[j].JobID != plannerID {
				rj = 999
			}
			if ri > rj {
				sorted[i], sorted[j] = sorted[j], sorted[i]
			}
		}
	}
	return sorted
}

func IsInvestigationTerminal(detail *api.InvestigationDetail, jobs []api.JobSummary) bool {
	if detail == nil {
		return false
	}
	if detail.Status == "closed" {
		return true
	}
	plan := detail.PlannerPlan
	if len(plan) > 0 {
		completed := make(map[string]bool)
		for _, p := range detail.CompletedPersonas {
			completed[p] = true
		}
		allDone := true
		for _, p := range plan {
			if !completed[p] {
				allDone = false
				break
			}
		}
		if allDone {
			return true
		}
	}
	if len(jobs) == 0 {
		return false
	}
	planSet := make(map[string]bool)
	for _, p := range plan {
		planSet[p] = true
	}
	var relevant []api.JobSummary
	for _, job := range jobs {
		if len(planSet) == 0 || planSet[job.Persona] {
			relevant = append(relevant, job)
		}
	}
	if len(relevant) == 0 {
		return false
	}
	for _, job := range relevant {
		if job.Status != "completed" && job.Status != "failed" {
			return false
		}
	}
	return true
}

func parsePlaybookSearchCount(preview string) int {
	preview = strings.TrimSpace(preview)
	if !strings.HasPrefix(preview, "{") {
		return -1
	}
	var parsed map[string]interface{}
	if err := json.Unmarshal([]byte(preview), &parsed); err != nil {
		return -1
	}
	if count, ok := parsed["count"].(float64); ok {
		return int(count)
	}
	if skills, ok := parsed["skills"].([]interface{}); ok {
		return len(skills)
	}
	return 0
}

func formatToolLabel(tool ToolCall) string {
	if !strings.HasPrefix(tool.Name, "playbook_search") {
		return tool.Name
	}
	query := tool.SearchQuery
	if query != "" {
		switch tool.Status {
		case "started":
			return fmt.Sprintf("playbook_search: %q", query)
		case "error":
			if tool.ErrorMessage != "" {
				return fmt.Sprintf("playbook_search: %q (%s)", query, tool.ErrorMessage)
			}
			return fmt.Sprintf("playbook_search: %q (error)", query)
		case "done":
			if tool.ResultCount >= 0 {
				return fmt.Sprintf("playbook_search: %d for %q", tool.ResultCount, query)
			}
			return fmt.Sprintf("playbook_search: %q", query)
		}
	}
	if tool.Status == "done" && tool.ResultCount >= 0 {
		return fmt.Sprintf("playbook_search: %d playbooks", tool.ResultCount)
	}
	return tool.Name
}

func resolveControlJobID(typ string, payload map[string]interface{}, engagementID string) string {
	if id := str(payload["job_id"]); id != "" {
		return id
	}
	if typ == "report" {
		return "coordinator:" + engagementID
	}
	return "critic:" + engagementID
}

func shouldApplyControlEvent(typ string, payload map[string]interface{}) bool {
	if typ == "report" {
		return false
	}
	if typ != "control" {
		return true
	}
	verdict, ok := payload["verdict"].(map[string]interface{})
	if !ok {
		return true
	}
	if boolVal(verdict["passed"]) && !boolVal(verdict["auto_accepted_after_revision_cap"]) && !boolVal(verdict["revision_enqueued"]) {
		return false
	}
	return true
}

func controlEventText(typ string, payload map[string]interface{}) string {
	switch typ {
	case "control_error":
		if msg := str(payload["error"]); msg != "" {
			return msg
		}
		return "control error"
	case "report":
		return str(payload["summary"])
	default:
		if msg := str(payload["operator_message"]); msg != "" {
			return msg
		}
		if verdict, ok := payload["verdict"].(map[string]interface{}); ok {
			source := str(payload["source_persona"])
			if source == "" {
				source = "agent"
			}
			if boolVal(verdict["auto_accepted_after_revision_cap"]) {
				return "Quality check for " + source + ": revision cap reached; result accepted automatically."
			}
			issues := append(stringList(verdict["issues_detected"]), stringList(verdict["rejected_claims"])...)
			if len(issues) > 0 {
				return "Quality check failed (" + source + "): " + strings.Join(issues, ", ") + ". Revision requested."
			}
			return jsonfmt.FormatValue(verdict)
		}
		return jsonfmt.FormatValue(payload)
	}
}

func stringList(v interface{}) []string {
	raw, ok := v.([]interface{})
	if !ok {
		return nil
	}
	out := make([]string, 0, len(raw))
	for _, item := range raw {
		text := strings.TrimSpace(fmt.Sprint(item))
		if text != "" {
			out = append(out, text)
		}
	}
	return out
}

func formatJobError(err string) string {
	switch {
	case strings.HasPrefix(err, "tools_not_executed:"):
		return "Tools were planned in JSON but never executed. " + err[len("tools_not_executed:"):]
	case strings.HasPrefix(err, "empty_finding:"):
		gaps := strings.ReplaceAll(err[len("empty_finding:"):], ",", ", ")
		return "Agent finished without a valid finding (missing: " + gaps + ")."
	case err == "empty_finding":
		return "Agent finished without a valid finding (model may have refused or returned invalid JSON)."
	case strings.HasPrefix(err, "model_refusal:"):
		return "Model refused: " + err[len("model_refusal:"):]
	case strings.HasPrefix(err, "ungrounded_finding:"):
		detail := strings.ReplaceAll(err[len("ungrounded_finding:"):], ",", ", ")
		return "Finding failed quality checks (evidence grounding): " + detail
	case strings.HasPrefix(err, "noop_finding"):
		return "Agent completed without a new substantive finding."
	default:
		return "Job failed: " + err
	}
}

func formatFindingText(finding interface{}) string {
	if data, ok := finding.(map[string]interface{}); ok {
		return jsonfmt.FormatFinding(data)
	}
	if parsed, ok := jsonfmt.ParseMaybe(fmt.Sprint(finding)); ok {
		return jsonfmt.FormatValue(parsed)
	}
	return fmt.Sprint(finding)
}

func str(v interface{}) string {
	if v == nil {
		return ""
	}
	switch t := v.(type) {
	case string:
		return t
	case float64:
		if t == float64(int64(t)) {
			return fmt.Sprintf("%d", int64(t))
		}
		return fmt.Sprintf("%v", t)
	default:
		return fmt.Sprint(t)
	}
}

func boolVal(v interface{}) bool {
	if b, ok := v.(bool); ok {
		return b
	}
	return false
}

func contains(slice []string, item string) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}
