package presentation

import (
	"strings"

	"github.com/butbeautifulv/egregore/tui/internal/api"
	"github.com/butbeautifulv/egregore/tui/internal/style"
)

// JobCells returns display cells for a job row.
func JobCells(j api.JobSummary) []string {
	status := style.StatusStyle(j.Status).Render(padStatus(j.Status))
	persona := style.Truncate(strings.TrimSpace(j.Persona), 16)
	jobID := style.Truncate(j.JobID, 24)
	return []string{status, persona, jobID}
}

// JobHeader returns column titles.
func JobHeader() []string {
	return []string{"Status", "Persona", "Job ID"}
}
