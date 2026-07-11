package components

import (
	"strings"
	"testing"

	"github.com/charmbracelet/lipgloss"
)

func TestRenderSectionTitle(t *testing.T) {
	out := RenderSectionTitle("Work orders", 20)
	if !strings.Contains(out, "Work orders") {
		t.Fatalf("got %q", out)
	}
	if lipgloss.Width(out) > 20 {
		t.Fatalf("width %d exceeds 20: %q", lipgloss.Width(out), out)
	}
}

func TestRenderTabsActive(t *testing.T) {
	out := RenderTabs([]string{"Chat", "Jobs", "Findings"}, 1, 80)
	if !strings.Contains(out, "Jobs") {
		t.Fatalf("got %q", out)
	}
}

func TestRenderTabsFitOnNarrowWidth(t *testing.T) {
	labels := []string{"Chat", "Jobs", "Findings", "Intake"}
	out := RenderTabs(labels, 0, 48)
	if strings.Contains(out, "…") {
		t.Fatalf("tabs truncated with ellipsis: %q", out)
	}
	for _, label := range labels {
		if !strings.Contains(out, label) {
			t.Fatalf("missing tab %q: %q", label, out)
		}
	}
	if lipgloss.Width(out) > 48 {
		t.Fatalf("width %d exceeds 48: %q", lipgloss.Width(out), out)
	}
}

func TestRenderKeybarTruncates(t *testing.T) {
	bindings := map[string]string{
		"q": "quit",
		"r": "refresh",
	}
	out := RenderKeybar(bindings, "API: http://127.0.0.1:8080", 40)
	if out == "" {
		t.Fatal("empty keybar")
	}
}
