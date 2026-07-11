package chat

import (
	"strings"
	"testing"

	"github.com/butbeautifulv/egregore/tui/internal/api"
)

func TestGroupFollowUpPairs(t *testing.T) {
	turns := []api.FollowUpTurn{
		{ID: "1", Role: "operator", Text: "question?", FollowUpID: "fu-1", CreatedAt: "2026-01-01T00:00:00Z"},
		{ID: "2", Role: "assistant", Text: "answer", FollowUpID: "fu-1", CreatedAt: "2026-01-01T00:01:00Z"},
	}
	pairs := GroupFollowUpPairs(turns)
	if len(pairs) != 1 {
		t.Fatalf("pairs %d want 1", len(pairs))
	}
	if pairs[0].Operator.Text != "question?" {
		t.Fatalf("operator text: %q", pairs[0].Operator.Text)
	}
	if pairs[0].Assistant == nil || pairs[0].Assistant.Text != "answer" {
		t.Fatalf("assistant: %+v", pairs[0].Assistant)
	}
}

func TestRenderFollowUpPairs(t *testing.T) {
	pairs := []FollowUpPair{{
		FollowUpID: "fu-1",
		Operator:   api.FollowUpTurn{Text: "hi"},
		Assistant:  &api.FollowUpTurn{Text: "hello"},
	}}
	out := RenderFollowUpPairs(pairs, 40)
	if !strings.Contains(out, "hi") || !strings.Contains(out, "hello") {
		t.Fatalf("missing content: %q", out)
	}
}
