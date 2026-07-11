package api

import "encoding/json"

type HealthResponse struct {
	Status   string `json:"status"`
	Features struct {
		StreamAgentOutput bool `json:"stream_agent_output"`
		StreamAgentTools  bool `json:"stream_agent_tools"`
	} `json:"features"`
}

type InfraHealthResponse struct {
	Status      string `json:"status"`
	Queue       struct {
		Backend string `json:"backend"`
		Depth   *int   `json:"depth"`
	} `json:"queue"`
	Egress struct {
		Backend string `json:"backend"`
	} `json:"egress"`
	BusTransport struct {
		Backend string `json:"backend"`
	} `json:"bus_transport"`
	WorkersHint  string `json:"workers_hint"`
	RunningJobs  int    `json:"running_jobs"`
}

type EngagementSummary struct {
	EngagementID       string                   `json:"engagement_id"`
	WorkOrderID        string                   `json:"work_order_id"`
	ProfileID          string                   `json:"profile_id"`
	Intake             map[string]interface{}   `json:"intake"`
	Status             string                   `json:"status"`
	LatestPhase        *string                  `json:"latest_phase"`
	JobIDs             []string                 `json:"job_ids"`
	Goal               string                   `json:"goal"`
	CompletedPersonas  []string                 `json:"completed_personas"`
	FailedPersonas     []string                 `json:"failed_personas"`
	PlannerPlan        []string                 `json:"planner_plan"`
	PlannerStatus      *string                  `json:"planner_status"`
	PlannerRationale   string                   `json:"planner_rationale"`
	PlannerError       string                   `json:"planner_error"`
	PlannerSubGoals    map[string]string        `json:"planner_sub_goals"`
	PlannerDependsOn   map[string][]string      `json:"planner_depends_on"`
	FindingsSummary    []map[string]interface{} `json:"findings_summary"`
	ExecutionMode      *string                  `json:"execution_mode"`
	SynthesisPersona   *string                  `json:"synthesis_persona"`
	FinalReport        map[string]interface{}   `json:"final_report"`
	UpdatedAt          string                   `json:"updated_at"`
}

type InvestigationSummary struct {
	InvestigationID   string   `json:"investigation_id"`
	TenantID          string   `json:"tenant_id"`
	Goal              string   `json:"goal"`
	Status            string   `json:"status"`
	CompletedPersonas []string `json:"completed_personas"`
	FailedPersonas    []string `json:"failed_personas"`
	UpdatedAt         string   `json:"updated_at"`
}

type InvestigationDetail struct {
	InvestigationSummary
	PlannerPlan      []string                 `json:"planner_plan"`
	PlannerStatus    *string                  `json:"planner_status"`
	PlannerRationale string                   `json:"planner_rationale"`
	PlannerError     string                   `json:"planner_error"`
	PlannerSubGoals  map[string]string        `json:"planner_sub_goals"`
	PlannerDependsOn map[string][]string      `json:"planner_depends_on"`
	FindingsSummary  []map[string]interface{} `json:"findings_summary"`
	FinalReport      map[string]interface{}   `json:"final_report"`
	LatestPhase      *string                  `json:"latest_phase"`
	ExecutionMode    *string                  `json:"execution_mode"`
	SynthesisPersona *string                  `json:"synthesis_persona"`
	Intake           map[string]interface{}   `json:"intake,omitempty"`
	ProfileID        string                   `json:"profile_id,omitempty"`
	WorkOrderID      string                   `json:"work_order_id,omitempty"`
}

type JobSummary struct {
	JobID         string `json:"job_id"`
	Persona       string `json:"persona"`
	Status        string `json:"status"`
	SessionID     string `json:"session_id"`
	CorrelationID string `json:"correlation_id"`
	EventID       string `json:"event_id"`
}

type PendingApproval struct {
	JobID      string                 `json:"job_id"`
	SessionID  string                 `json:"session_id"`
	Persona    string                 `json:"persona"`
	ToolName   string                 `json:"tool_name"`
	ToolArgs   map[string]interface{} `json:"tool_args"`
	RiskLevel  string                 `json:"risk_level"`
	ApprovalID string                 `json:"approval_id"`
}

type EngagementStreamEvent struct {
	Type    string                 `json:"type"`
	Phase   string                 `json:"phase"`
	TS      string                 `json:"ts"`
	Payload map[string]interface{} `json:"payload"`
}

type StatusStreamEvent struct {
	Kind    string                 `json:"kind"`
	Payload map[string]interface{} `json:"payload"`
	TS      string                 `json:"ts"`
	ID      string                 `json:"id"`
}

type CatalogAgent struct {
	Name            string   `json:"name"`
	Description     string   `json:"description"`
	Role            string   `json:"role"`
	Tools           []string `json:"tools"`
	Skills          []string `json:"skills"`
	ProfileID       string   `json:"profile_id"`
	Version         int      `json:"version"`
	VersionTag      string   `json:"version_tag"`
	Enabled         bool     `json:"enabled"`
	EmpiricalTrust  float64  `json:"empirical_trust"`
}

type CatalogAgentDetail struct {
	CatalogAgent
	SystemPrompt       string `json:"system_prompt"`
	SystemPromptDigest string `json:"system_prompt_digest"`
}

type CatalogSkill struct {
	SkillID        string `json:"id"`
	Name           string `json:"name"`
	Description    string `json:"description"`
	Body           string `json:"body"`
	Version        int    `json:"version"`
	Enabled        bool   `json:"enabled"`
	ApprovalStatus string `json:"staging_status"`
}

// CatalogSkillID returns the skill identifier, falling back to name.
func (s CatalogSkill) CatalogSkillID() string {
	if s.SkillID != "" {
		return s.SkillID
	}
	return s.Name
}

type CatalogTool struct {
	ToolID      string `json:"id"`
	Name        string `json:"name"`
	Description string `json:"description"`
	RiskTier    string `json:"risk_tier"`
	Enabled     bool   `json:"enabled"`
}

// CatalogToolID returns the tool identifier, falling back to name.
func (t CatalogTool) CatalogToolID() string {
	if t.ToolID != "" {
		return t.ToolID
	}
	return t.Name
}

type CatalogPlan struct {
	PlanID      string   `json:"id"`
	Name        string   `json:"name"`
	Description string   `json:"description"`
	Personas    []string `json:"personas"`
	Active      bool     `json:"active"`
}

// CatalogPlanID returns the plan identifier, falling back to name.
func (p CatalogPlan) CatalogPlanID() string {
	if p.PlanID != "" {
		return p.PlanID
	}
	return p.Name
}

type MemoryEntry struct {
	ID             string                 `json:"id"`
	InvestigationID string                `json:"investigation_id"`
	SourceAgent    string                 `json:"source_agent"`
	SourceJobID    string                 `json:"source_job_id"`
	MemoryType     string                 `json:"memory_type"`
	TrustScore     float64                `json:"trust_score"`
	Content        string                 `json:"content"`
	ContentParsed  map[string]interface{} `json:"content_parsed"`
	CreatedAt      string                 `json:"created_at"`
}

type FollowUpTurn struct {
	ID         string  `json:"id"`
	Role       string  `json:"role"`
	Text       string  `json:"text"`
	CreatedAt  string  `json:"created_at"`
	FollowUpID string  `json:"follow_up_id"`
	JobID      *string `json:"job_id"`
	Persona    *string `json:"persona"`
	Status     string  `json:"status"`
}

type FollowUpListResponse struct {
	Turns []FollowUpTurn `json:"turns"`
}

type FollowUpSendResponse struct {
	FollowUpID string  `json:"follow_up_id"`
	Status     string  `json:"status"`
	WorkKind   string  `json:"work_kind"`
	JobID      *string `json:"job_id"`
}

type APIFeatures struct {
	StreamAgentOutput bool
	StreamAgentTools  bool
}

func (e EngagementStreamEvent) PayloadString(key string) string {
	if e.Payload == nil {
		return ""
	}
	v, ok := e.Payload[key]
	if !ok || v == nil {
		return ""
	}
	switch t := v.(type) {
	case string:
		return t
	default:
		b, _ := json.Marshal(t)
		return string(b)
	}
}
