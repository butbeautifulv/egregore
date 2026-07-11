package jsonfmt

import (
	"strings"
	"testing"
)

func TestFormatMessageMixedProseJSON(t *testing.T) {
	text := "Здравствуйте!\n\nВот план:\n{\"personas\":[\"consultant\"],\"rationale\":\"test\"}"
	out := FormatMessage(text, 80)
	if !strings.Contains(out, "Здравствуйте") {
		t.Fatalf("missing prose: %q", out)
	}
	if !strings.Contains(out, "Planner plan") {
		t.Fatalf("missing planner format: %q", out)
	}
	if strings.Contains(out, "\ufffd") {
		t.Fatalf("broken utf8: %q", out)
	}
}

func TestFormatFindingSummary(t *testing.T) {
	data := map[string]interface{}{
		"summary":    "Suspicious login",
		"risk_level": "high",
		"evidence":   []interface{}{"auth.log:42"},
	}
	out := FormatFinding(data)
	if !strings.Contains(out, "Summary:") || !strings.Contains(out, "Suspicious login") {
		t.Fatalf("unexpected: %q", out)
	}
}

func TestFormatMessageJSONThenProse(t *testing.T) {
	text := `{"personas":["consultant"],"rationale":"test"}Здравствуйте!`
	out := FormatMessage(text, 80)
	if !strings.Contains(out, "Planner plan") {
		t.Fatalf("missing planner format: %q", out)
	}
	if !strings.Contains(out, "Здравствуйте") {
		t.Fatalf("missing trailing prose: %q", out)
	}
}

func TestParseMaybePlanner(t *testing.T) {
	raw := `{"planner_plan":["soc"],"planner_rationale":"because"}`
	parsed, ok := ParseMaybe(raw)
	if !ok {
		t.Fatal("expected parse")
	}
	m := parsed.(map[string]interface{})
	out := FormatPlanner(m)
	if !strings.Contains(out, "soc") || !strings.Contains(out, "because") {
		t.Fatalf("unexpected: %q", out)
	}
}
