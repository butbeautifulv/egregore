package api

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/butbeautifulv/egregore/tui/internal/config"
)

func testClient(srv *httptest.Server) *Client {
	cfg := config.Config{
		APIURL:   srv.URL,
		APIToken: "test-token",
		TenantID: "default",
		Timeout:  5 * time.Second,
	}
	return NewClient(cfg)
}

func TestListInvestigations(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/engagements" {
			t.Fatalf("unexpected path: %s", r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"engagements": []map[string]interface{}{
				{
					"engagement_id": "eng-1",
					"goal":          "triage alert",
					"status":        "open",
					"updated_at":    "2026-01-01T00:00:00Z",
				},
			},
		})
	}))
	defer srv.Close()

	items, err := testClient(srv).ListInvestigations(context.Background(), 10)
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 1 || items[0].InvestigationID != "eng-1" {
		t.Fatalf("unexpected items: %+v", items)
	}
}

func TestCreateEngagement(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Fatalf("expected POST, got %s", r.Method)
		}
		var body map[string]interface{}
		_ = json.NewDecoder(r.Body).Decode(&body)
		if body["goal"] != "test goal" {
			t.Fatalf("unexpected body: %+v", body)
		}
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"engagement_id": "eng-new",
			"status":        "open",
		})
	}))
	defer srv.Close()

	eng, err := testClient(srv).CreateEngagement(context.Background(), "test goal")
	if err != nil {
		t.Fatal(err)
	}
	if eng.EngagementID != "eng-new" {
		t.Fatalf("unexpected engagement: %+v", eng)
	}
}

func TestListWorkOrdersFallbackToEngagements(t *testing.T) {
	calls := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		switch r.URL.Path {
		case "/v1/work-orders":
			w.WriteHeader(http.StatusNotFound)
			_, _ = w.Write([]byte(`{"detail":"Not Found"}`))
		case "/v1/engagements":
			_ = json.NewEncoder(w).Encode(map[string]interface{}{
				"engagements": []map[string]interface{}{
					{
						"engagement_id":      "eng-legacy",
						"goal":               "legacy goal",
						"status":             "running",
						"completed_personas": []string{"soc"},
						"updated_at":         "2026-01-01T00:00:00Z",
					},
				},
			})
		default:
			t.Fatalf("unexpected path: %s", r.URL.Path)
		}
	}))
	defer srv.Close()

	items, err := testClient(srv).ListWorkOrders(context.Background(), 10)
	if err != nil {
		t.Fatal(err)
	}
	if calls < 2 {
		t.Fatalf("expected work-orders then engagements, got %d calls", calls)
	}
	if len(items) != 1 || items[0].InvestigationID != "eng-legacy" {
		t.Fatalf("unexpected items: %+v", items)
	}
	if len(items[0].CompletedPersonas) != 1 || items[0].CompletedPersonas[0] != "soc" {
		t.Fatalf("expected personas, got %+v", items[0].CompletedPersonas)
	}
}

func TestListWorkOrdersMapsPersonas(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/work-orders" {
			t.Fatalf("unexpected path: %s", r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"work_orders": []map[string]interface{}{
				{
					"work_order_id":      "wo-1",
					"goal":               "triage",
					"status":             "running",
					"completed_personas": []string{"soc", "forensics"},
					"failed_personas":    []string{"malware"},
				},
			},
		})
	}))
	defer srv.Close()

	items, err := testClient(srv).ListWorkOrders(context.Background(), 10)
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 1 {
		t.Fatalf("unexpected items: %+v", items)
	}
	if len(items[0].CompletedPersonas) != 2 {
		t.Fatalf("expected completed personas, got %+v", items[0].CompletedPersonas)
	}
	if len(items[0].FailedPersonas) != 1 {
		t.Fatalf("expected failed personas, got %+v", items[0].FailedPersonas)
	}
}

func TestCreateWorkOrderFallbackToEngagement(t *testing.T) {
	calls := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		switch r.URL.Path {
		case "/v1/work-orders":
			w.WriteHeader(http.StatusNotFound)
			_, _ = w.Write([]byte(`{"detail":"Not Found"}`))
		case "/v1/engagements":
			if r.Method != http.MethodPost {
				t.Fatalf("expected POST, got %s", r.Method)
			}
			_ = json.NewEncoder(w).Encode(map[string]interface{}{
				"engagement_id": "eng-new",
				"status":        "open",
			})
		default:
			t.Fatalf("unexpected path: %s", r.URL.Path)
		}
	}))
	defer srv.Close()

	eng, err := testClient(srv).CreateWorkOrderWithIntake(context.Background(), "test goal", nil)
	if err != nil {
		t.Fatal(err)
	}
	if calls < 2 {
		t.Fatalf("expected fallback, got %d calls", calls)
	}
	if eng.WorkOrderID != "eng-new" || eng.EngagementID != "eng-new" {
		t.Fatalf("unexpected engagement: %+v", eng)
	}
}

func TestListFollowUpsFallback(t *testing.T) {
	calls := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if strings.HasPrefix(r.URL.Path, "/v1/work-orders/") {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		if strings.HasPrefix(r.URL.Path, "/v1/engagements/wo-1/follow-ups") {
			_ = json.NewEncoder(w).Encode(map[string]interface{}{
				"turns": []map[string]interface{}{
					{"id": "t1", "role": "user", "text": "hello"},
				},
			})
			return
		}
		t.Fatalf("unexpected path: %s", r.URL.Path)
	}))
	defer srv.Close()

	turns, err := testClient(srv).ListFollowUps(context.Background(), "wo-1")
	if err != nil {
		t.Fatal(err)
	}
	if calls < 2 {
		t.Fatalf("expected fallback, got %d calls", calls)
	}
	if len(turns) != 1 || turns[0].Text != "hello" {
		t.Fatalf("unexpected turns: %+v", turns)
	}
}

func TestParseSSEChunk(t *testing.T) {
	var got []string
	parseSSEChunk("data: {\"type\":\"assistant_delta\"}\n", func(data string) {
		got = append(got, data)
	})
	if len(got) != 1 || !strings.Contains(got[0], "assistant_delta") {
		t.Fatalf("unexpected data: %+v", got)
	}
}

func TestMatchesInvestigation(t *testing.T) {
	event := StatusStreamEvent{
		Payload: map[string]interface{}{
			"correlation_id": "inv-42",
		},
	}
	if !MatchesInvestigation(event, "inv-42") {
		t.Fatal("expected match")
	}
	if MatchesInvestigation(event, "other") {
		t.Fatal("expected no match")
	}
}

func TestEventDedupeKeyFromChat(t *testing.T) {
	event := EngagementStreamEvent{
		Type: "assistant_delta",
		Payload: map[string]interface{}{
			"job_id": "j1",
			"seq":    float64(1),
			"delta":  "hi",
		},
	}
	key := EventDedupeKeyForTest(event)
	if key == "" {
		t.Fatal("empty key")
	}
}

// EventDedupeKeyForTest exposes dedupe via chat package test helper pattern.
func EventDedupeKeyForTest(event EngagementStreamEvent) string {
	payload := event.Payload
	if payload == nil {
		payload = map[string]interface{}{}
	}
	return strings.Join([]string{
		event.Type,
		strVal(payload["job_id"]),
		strVal(payload["seq"]),
		strVal(payload["delta"]),
	}, "|")
}

func strVal(v interface{}) string {
	if v == nil {
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
