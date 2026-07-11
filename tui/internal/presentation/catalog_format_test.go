package presentation

import (
	"testing"

	"github.com/charmbracelet/lipgloss"
)

func TestFormatPairFitsWidth(t *testing.T) {
	out := FormatPair("long-agent-name", "security-analyst-role", 28)
	if lipgloss.Width(out) > 28 {
		t.Fatalf("width %d exceeds 28: %q", lipgloss.Width(out), out)
	}
}

func TestWorkOrderColumnSpecsForWidthNarrow(t *testing.T) {
	specs := WorkOrderColumnSpecsForWidth(30)
	if len(specs) != 2 {
		t.Fatalf("narrow specs: got %d columns", len(specs))
	}
}
