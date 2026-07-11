package presentation

import (
	"strings"
	"testing"

	"github.com/butbeautifulv/egregore/tui/internal/api"
)

func TestWorkOrderCellsStatusColors(t *testing.T) {
	cases := []string{"running", "failed", "open"}
	for _, status := range cases {
		cells := WorkOrderCells(api.InvestigationSummary{
			InvestigationID: "wo-1",
			Goal:          "test goal",
			Status:        status,
			UpdatedAt:     "2026-01-01T12:00:00Z",
		})
		if !strings.Contains(cells[0], status) {
			t.Fatalf("status %q: got %q", status, cells[0])
		}
	}
}
