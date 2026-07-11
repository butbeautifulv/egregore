package detail

import (
	"testing"

	"github.com/butbeautifulv/egregore/tui/internal/api"
)

func TestCanComposeFollowUpClosedOnly(t *testing.T) {
	if CanComposeFollowUp(nil) {
		t.Fatal("nil detail")
	}
	if CanComposeFollowUp(&api.InvestigationDetail{
		InvestigationSummary: api.InvestigationSummary{Status: "running"},
	}) {
		t.Fatal("running should not compose")
	}
	if !CanComposeFollowUp(&api.InvestigationDetail{
		InvestigationSummary: api.InvestigationSummary{Status: "closed"},
	}) {
		t.Fatal("closed should compose")
	}
}

func TestChromeBudgetChatComposer(t *testing.T) {
	m := Model{
		tab:         TabChat,
		workOrderID: "wo-1",
		height:      20,
		detail: &api.InvestigationDetail{
			InvestigationSummary: api.InvestigationSummary{Status: "closed"},
		},
	}
	b := m.chromeBudget()
	if b.Composer < 1 {
		t.Fatalf("expected composer chrome, got %+v", b)
	}
	if b.Total() >= m.height {
		t.Fatalf("chrome consumes entire height: %d >= %d", b.Total(), m.height)
	}
}
