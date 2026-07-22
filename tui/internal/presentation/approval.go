package presentation

import (
	"strings"

	"github.com/butbeautifulv/egregore/tui/internal/api"
	"github.com/butbeautifulv/egregore/tui/internal/style"
)

// ApprovalCells returns display cells for an approval row.
func ApprovalCells(a api.PendingApproval) []string {
	status := style.StatusStyle("pending").Render("pending")
	persona := style.Truncate(a.Persona, 12)
	tool := style.Truncate(a.ToolName, 20)
	risk := style.Truncate(a.RiskLevel, 8)
	workOrder := style.Truncate(a.CorrelationID, 16)
	return []string{status, persona, tool, risk, workOrder}
}

// ApprovalHeader returns column titles.
func ApprovalHeader() []string {
	return []string{"Status", "Persona", "Tool", "Risk", "Work order"}
}

// ApprovalJobID returns trimmed job id for display.
func ApprovalJobID(a api.PendingApproval) string {
	return strings.TrimSpace(a.JobID)
}
