package chat

import (
	"testing"

	"github.com/butbeautifulv/egregore/tui/internal/api"
)

func TestEventDedupeKey(t *testing.T) {
	event := api.EngagementStreamEvent{
		Type: "assistant_delta",
		Payload: map[string]interface{}{
			"job_id": "job-1",
			"seq":    float64(2),
			"delta":  "hello",
		},
	}
	key := EventDedupeKey(event)
	if key == "" {
		t.Fatal("expected non-empty dedupe key")
	}
	dup := EventDedupeKey(event)
	if key != dup {
		t.Fatal("dedupe key should be stable")
	}
}

func TestApplyChatEventAssistantDelta(t *testing.T) {
	state := NewState()
	features := api.APIFeatures{StreamAgentTools: true}
	event := api.EngagementStreamEvent{
		Type: "assistant_delta",
		Payload: map[string]interface{}{
			"job_id":  "job-1",
			"persona": "soc",
			"delta":   "Hello",
		},
	}
	changed := state.ApplyEvent(event, features, "eng-1")
	if !changed {
		t.Fatal("expected change")
	}
	entry := state.Get("job-1")
	if entry == nil || entry.Buffer != "Hello" || !entry.Streaming {
		t.Fatalf("unexpected entry: %+v", entry)
	}
}

func TestApplyChatEventAssistantDone(t *testing.T) {
	state := NewState()
	features := api.APIFeatures{}
	state.Ensure("job-1", "soc").Buffer = "done text"

	event := api.EngagementStreamEvent{
		Type: "assistant_done",
		Payload: map[string]interface{}{
			"job_id": "job-1",
		},
	}
	state.ApplyEvent(event, features, "eng-1")
	entry := state.Get("job-1")
	if len(entry.Turns) != 1 || entry.Turns[0] != "done text" || entry.Buffer != "" {
		t.Fatalf("unexpected entry after done: %+v", entry)
	}
}

func TestShouldRefreshOnEvent(t *testing.T) {
	if !ShouldRefreshOnEvent(api.EngagementStreamEvent{Type: "job_finished"}) {
		t.Fatal("job_finished should refresh")
	}
	if ShouldRefreshOnEvent(api.EngagementStreamEvent{Type: "assistant_delta"}) {
		t.Fatal("assistant_delta should not refresh")
	}
}

func TestIsInvestigationTerminalClosed(t *testing.T) {
	detail := &api.InvestigationDetail{
		InvestigationSummary: api.InvestigationSummary{Status: "closed"},
	}
	if !IsInvestigationTerminal(detail, nil) {
		t.Fatal("closed should be terminal")
	}
}

func TestSortEntriesPlannerFirst(t *testing.T) {
	state := NewState()
	state.Ensure("job-b", "network")
	state.Ensure("planner:eng-1", "planner")
	state.Ensure("job-a", "soc")

	sorted := SortEntries(state.Entries(), "planner:eng-1", []string{"soc", "network"}, []api.JobSummary{
		{JobID: "job-a", Persona: "soc"},
		{JobID: "job-b", Persona: "network"},
	})
	if sorted[0].JobID != "planner:eng-1" {
		t.Fatalf("planner should be first, got %s", sorted[0].JobID)
	}
}
