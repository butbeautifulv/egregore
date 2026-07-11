package api

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/butbeautifulv/egregore/tui/internal/config"
)

type APIError struct {
	Status  int
	Message string
}

func (e *APIError) Error() string {
	return fmt.Sprintf("API %d: %s", e.Status, e.Message)
}

func isNotFoundError(err error) bool {
	var apiErr *APIError
	if errors.As(err, &apiErr) {
		return apiErr.Status == http.StatusNotFound
	}
	return false
}

type Client struct {
	baseURL  string
	token    string
	tenantID string
	timeout  time.Duration
	http     *http.Client
}

func NewClient(cfg config.Config) *Client {
	return &Client{
		baseURL:  cfg.APIURL,
		token:    cfg.APIToken,
		tenantID: cfg.TenantID,
		timeout:  cfg.Timeout,
		http: &http.Client{
			Timeout: cfg.Timeout,
		},
	}
}

func (c *Client) TenantID() string { return c.tenantID }

func (c *Client) authHeaders() http.Header {
	h := make(http.Header)
	h.Set("Content-Type", "application/json")
	if c.token != "" {
		h.Set("Authorization", "Bearer "+c.token)
	}
	return h
}

func (c *Client) request(ctx context.Context, method, path string, body any, out any) error {
	var reader io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return err
		}
		reader = bytes.NewReader(b)
	}

	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, reader)
	if err != nil {
		return err
	}
	req.Header = c.authHeaders()

	resp, err := c.http.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		b, _ := io.ReadAll(resp.Body)
		msg := strings.TrimSpace(string(b))
		if msg == "" {
			msg = resp.Status
		}
		return &APIError{Status: resp.StatusCode, Message: msg}
	}

	if out == nil || resp.StatusCode == http.StatusNoContent {
		return nil
	}
	return json.NewDecoder(resp.Body).Decode(out)
}

func (c *Client) GetHealth(ctx context.Context) (*HealthResponse, error) {
	var out HealthResponse
	if err := c.request(ctx, http.MethodGet, "/health", nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (c *Client) GetHealthInfra(ctx context.Context) (*InfraHealthResponse, error) {
	var out InfraHealthResponse
	if err := c.request(ctx, http.MethodGet, "/health/infra", nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (c *Client) ListInvestigations(ctx context.Context, limit int) ([]InvestigationSummary, error) {
	path := fmt.Sprintf("/v1/engagements?tenant_id=%s&limit=%d",
		url.QueryEscape(c.tenantID), limit)
	var data struct {
		Engagements []EngagementSummary `json:"engagements"`
	}
	if err := c.request(ctx, http.MethodGet, path, nil, &data); err != nil {
		return nil, err
	}
	out := make([]InvestigationSummary, 0, len(data.Engagements))
	for _, eng := range data.Engagements {
		out = append(out, InvestigationSummary{
			InvestigationID:   eng.EngagementID,
			TenantID:          c.tenantID,
			Goal:              eng.Goal,
			Status:            eng.Status,
			CompletedPersonas: eng.CompletedPersonas,
			FailedPersonas:    eng.FailedPersonas,
			UpdatedAt:         eng.UpdatedAt,
		})
	}
	return out, nil
}

func (c *Client) CreateEngagement(ctx context.Context, goal string) (*EngagementSummary, error) {
	body := map[string]interface{}{
		"goal":          goal,
		"plan_strategy": "meta_llm",
		"mode":          "async",
		"tenant_id":     c.tenantID,
	}
	var out EngagementSummary
	if err := c.request(ctx, http.MethodPost, "/v1/engagements", body, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (c *Client) CreateWorkOrder(ctx context.Context, goal string) (*EngagementSummary, error) {
	return c.CreateWorkOrderWithIntake(ctx, goal, nil)
}

func (c *Client) CreateWorkOrderWithIntake(ctx context.Context, goal string, intake map[string]interface{}) (*EngagementSummary, error) {
	body := map[string]interface{}{
		"plan_strategy": "meta_llm",
		"mode":          "async",
		"tenant_id":     c.tenantID,
		"profile_id":    "cybersec-soc",
	}
	if strings.TrimSpace(goal) != "" {
		body["goal"] = strings.TrimSpace(goal)
	}
	if len(intake) > 0 {
		body["intake"] = intake
	}
	var out EngagementSummary
	if err := c.request(ctx, http.MethodPost, "/v1/work-orders", body, &out); err != nil {
		if !isNotFoundError(err) {
			return nil, err
		}
		legacyBody := map[string]interface{}{
			"plan_strategy": "meta_llm",
			"mode":          "async",
			"tenant_id":     c.tenantID,
			"profile_id":    "cybersec-soc",
		}
		effectiveGoal := strings.TrimSpace(goal)
		if effectiveGoal == "" && intake != nil {
			if g, ok := intake["goal"].(string); ok {
				effectiveGoal = strings.TrimSpace(g)
			}
		}
		if effectiveGoal != "" {
			legacyBody["goal"] = effectiveGoal
		}
		if len(intake) > 0 {
			legacyBody["input"] = intake
		}
		var legacy EngagementSummary
		if err := c.request(ctx, http.MethodPost, "/v1/engagements", legacyBody, &legacy); err != nil {
			return nil, err
		}
		legacy.WorkOrderID = legacy.EngagementID
		return &legacy, nil
	}
	if out.EngagementID == "" {
		out.EngagementID = out.WorkOrderID
	}
	return &out, nil
}

func mapWorkOrderSummary(wo EngagementSummary, tenantID string) InvestigationSummary {
	id := wo.WorkOrderID
	if id == "" {
		id = wo.EngagementID
	}
	return InvestigationSummary{
		InvestigationID:   id,
		TenantID:          tenantID,
		Goal:              wo.Goal,
		Status:            wo.Status,
		CompletedPersonas: wo.CompletedPersonas,
		FailedPersonas:    wo.FailedPersonas,
		UpdatedAt:         wo.UpdatedAt,
	}
}

func (c *Client) ListWorkOrders(ctx context.Context, limit int) ([]InvestigationSummary, error) {
	path := fmt.Sprintf("/v1/work-orders?tenant_id=%s&limit=%d",
		url.QueryEscape(c.tenantID), limit)
	var data struct {
		WorkOrders []EngagementSummary `json:"work_orders"`
	}
	if err := c.request(ctx, http.MethodGet, path, nil, &data); err != nil {
		if !isNotFoundError(err) {
			return nil, err
		}
		return c.ListInvestigations(ctx, limit)
	}
	out := make([]InvestigationSummary, 0, len(data.WorkOrders))
	for _, wo := range data.WorkOrders {
		out = append(out, mapWorkOrderSummary(wo, c.tenantID))
	}
	return out, nil
}

func (c *Client) GetInvestigation(ctx context.Context, id string) (*InvestigationDetail, error) {
	woPath := fmt.Sprintf("/v1/work-orders/%s?tenant_id=%s",
		url.PathEscape(id), url.QueryEscape(c.tenantID))
	var wo EngagementSummary
	_ = c.request(ctx, http.MethodGet, woPath, nil, &wo)

	engPath := fmt.Sprintf("/v1/engagements/%s?tenant_id=%s",
		url.PathEscape(id), url.QueryEscape(c.tenantID))
	var eng EngagementSummary
	if err := c.request(ctx, http.MethodGet, engPath, nil, &eng); err != nil {
		if wo.WorkOrderID == "" && wo.EngagementID == "" {
			return nil, err
		}
		return mapEngagementToInvestigation(wo, c.tenantID), nil
	}
	detail := mapEngagementToInvestigation(eng, c.tenantID)
	if wo.WorkOrderID != "" {
		detail.WorkOrderID = wo.WorkOrderID
		detail.InvestigationID = wo.WorkOrderID
	}
	if wo.ProfileID != "" {
		detail.ProfileID = wo.ProfileID
	}
	if len(wo.Intake) > 0 {
		detail.Intake = wo.Intake
	}
	if detail.Goal == "" {
		detail.Goal = wo.Goal
	}
	return detail, nil
}

func mapEngagementToInvestigation(eng EngagementSummary, tenantID string) *InvestigationDetail {
	return &InvestigationDetail{
		InvestigationSummary: InvestigationSummary{
			InvestigationID:   eng.EngagementID,
			TenantID:          tenantID,
			Goal:              eng.Goal,
			Status:            eng.Status,
			CompletedPersonas: eng.CompletedPersonas,
			FailedPersonas:    eng.FailedPersonas,
			UpdatedAt:         eng.UpdatedAt,
		},
		PlannerPlan:      eng.PlannerPlan,
		PlannerStatus:    eng.PlannerStatus,
		PlannerRationale: eng.PlannerRationale,
		PlannerError:     eng.PlannerError,
		PlannerSubGoals:  eng.PlannerSubGoals,
		PlannerDependsOn: eng.PlannerDependsOn,
		FindingsSummary:  eng.FindingsSummary,
		FinalReport:      eng.FinalReport,
		LatestPhase:      eng.LatestPhase,
		ExecutionMode:    eng.ExecutionMode,
		SynthesisPersona: eng.SynthesisPersona,
	}
}

func (c *Client) GetInvestigationJobs(ctx context.Context, id string) ([]JobSummary, error) {
	path := fmt.Sprintf("/investigations/%s/jobs?tenant_id=%s",
		url.PathEscape(id), url.QueryEscape(c.tenantID))
	var data struct {
		Jobs []JobSummary `json:"jobs"`
	}
	if err := c.request(ctx, http.MethodGet, path, nil, &data); err != nil {
		return nil, err
	}
	return data.Jobs, nil
}

func (c *Client) ListPendingApprovals(ctx context.Context) ([]PendingApproval, error) {
	var data struct {
		Count     int               `json:"count"`
		Approvals []PendingApproval `json:"approvals"`
	}
	if err := c.request(ctx, http.MethodGet, "/approvals/pending", nil, &data); err != nil {
		return nil, err
	}
	return data.Approvals, nil
}

func (c *Client) ResumeJob(ctx context.Context, jobID, decision, approvalID string) error {
	body := map[string]interface{}{
		"decision": decision,
		"actor":    "operator-tui",
	}
	if approvalID != "" {
		body["approval_id"] = approvalID
	}
	return c.request(ctx, http.MethodPost,
		fmt.Sprintf("/jobs/%s/resume", url.PathEscape(jobID)), body, nil)
}

func (c *Client) ListCatalogAgents(ctx context.Context) ([]CatalogAgent, error) {
	var data struct {
		Agents []CatalogAgent `json:"agents"`
	}
	if err := c.request(ctx, http.MethodGet, "/catalog/agents", nil, &data); err != nil {
		return nil, err
	}
	return data.Agents, nil
}

func (c *Client) GetCatalogAgent(ctx context.Context, name string) (*CatalogAgentDetail, error) {
	var out CatalogAgentDetail
	if err := c.request(ctx, http.MethodGet,
		fmt.Sprintf("/catalog/agents/%s", url.PathEscape(name)), nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (c *Client) ListCatalogSkills(ctx context.Context) ([]CatalogSkill, error) {
	var data struct {
		Skills []CatalogSkill `json:"skills"`
	}
	if err := c.request(ctx, http.MethodGet, "/catalog/skills", nil, &data); err != nil {
		return nil, err
	}
	return data.Skills, nil
}

func (c *Client) GetCatalogSkill(ctx context.Context, skillID string) (*CatalogSkill, error) {
	var out CatalogSkill
	if err := c.request(ctx, http.MethodGet,
		fmt.Sprintf("/catalog/skills/%s", url.PathEscape(skillID)), nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (c *Client) ListCatalogTools(ctx context.Context) ([]CatalogTool, error) {
	var data struct {
		Tools []CatalogTool `json:"tools"`
	}
	if err := c.request(ctx, http.MethodGet, "/catalog/tools", nil, &data); err != nil {
		return nil, err
	}
	return data.Tools, nil
}

func (c *Client) ListCatalogPlans(ctx context.Context) ([]CatalogPlan, error) {
	var data struct {
		Plans []CatalogPlan `json:"plans"`
	}
	if err := c.request(ctx, http.MethodGet, "/catalog/plans", nil, &data); err != nil {
		return nil, err
	}
	return data.Plans, nil
}

func (c *Client) ListTenantMemory(ctx context.Context, agent string, limit int) ([]MemoryEntry, error) {
	params := url.Values{"tenant_id": {c.tenantID}}
	if agent != "" {
		params.Set("agent", agent)
	}
	if limit > 0 {
		params.Set("limit", fmt.Sprintf("%d", limit))
	}
	var data struct {
		Entries []MemoryEntry `json:"entries"`
	}
	if err := c.request(ctx, http.MethodGet, "/v1/memory?"+params.Encode(), nil, &data); err != nil {
		return nil, err
	}
	return data.Entries, nil
}

func (c *Client) EngagementStreamURL(engagementID string) string {
	return fmt.Sprintf("%s/v1/engagements/%s/stream?tenant_id=%s",
		c.baseURL, url.PathEscape(engagementID), url.QueryEscape(c.tenantID))
}

func (c *Client) StatusStreamURL() string {
	return c.baseURL + "/status/stream"
}

func (c *Client) StreamRequest(ctx context.Context, streamURL string) (*http.Response, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, streamURL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "text/event-stream")
	req.Header.Set("Authorization", "Bearer "+c.token)

	// No client-level timeout for streaming.
	streamClient := &http.Client{Timeout: 0}
	return streamClient.Do(req)
}

func (c *Client) Timeout() time.Duration { return c.timeout }

func (c *Client) ListFollowUps(ctx context.Context, workOrderID string) ([]FollowUpTurn, error) {
	path := fmt.Sprintf("/v1/work-orders/%s/follow-ups?tenant_id=%s",
		url.PathEscape(workOrderID), url.QueryEscape(c.tenantID))
	var data FollowUpListResponse
	if err := c.request(ctx, http.MethodGet, path, nil, &data); err != nil {
		if !isNotFoundError(err) {
			return nil, err
		}
		legacyPath := fmt.Sprintf("/v1/engagements/%s/follow-ups?tenant_id=%s",
			url.PathEscape(workOrderID), url.QueryEscape(c.tenantID))
		if err := c.request(ctx, http.MethodGet, legacyPath, nil, &data); err != nil {
			return nil, err
		}
	}
	return data.Turns, nil
}

func (c *Client) SendFollowUp(ctx context.Context, workOrderID, message string) (*FollowUpSendResponse, error) {
	path := fmt.Sprintf("/v1/work-orders/%s/follow-ups", url.PathEscape(workOrderID))
	body := map[string]interface{}{
		"message":   message,
		"tenant_id": c.tenantID,
		"mode":      "auto",
		"enqueue":   true,
	}
	var out FollowUpSendResponse
	if err := c.request(ctx, http.MethodPost, path, body, &out); err != nil {
		if !isNotFoundError(err) {
			return nil, err
		}
		legacyPath := fmt.Sprintf("/v1/engagements/%s/follow-ups", url.PathEscape(workOrderID))
		if err := c.request(ctx, http.MethodPost, legacyPath, body, &out); err != nil {
			return nil, err
		}
	}
	return &out, nil
}
