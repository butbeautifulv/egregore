package chat

import (
	"fmt"
	"strings"

	"github.com/butbeautifulv/egregore/tui/internal/api"
	"github.com/butbeautifulv/egregore/tui/internal/jsonfmt"
	"github.com/butbeautifulv/egregore/tui/internal/textutil"
)

// RenderOptions controls chat text output.
type RenderOptions struct {
	ShowReasoning bool
	Width         int
}

func RenderFindings(detail *api.InvestigationDetail, width int) string {
	if detail == nil || len(detail.FindingsSummary) == 0 {
		return "No structured findings yet."
	}
	if width < 10 {
		width = 10
	}
	return textutil.WrapBlock(jsonfmt.FormatFindingsSummary(detail.FindingsSummary), width)
}

func renderEntry(entry *Entry, opts RenderOptions, width int) string {
	var b strings.Builder
	header := fmt.Sprintf("▸ %s (%s)", entry.Persona, entry.JobID)
	if entry.JobError != "" {
		header += " [error]"
	}
	if entry.IsControlError {
		header += " [control error]"
	}
	b.WriteString(textutil.WrapLine(header, width))
	b.WriteString("\n")

	if opts.ShowReasoning && entry.Reasoning != nil {
		r := entry.Reasoning
		b.WriteString(textutil.WrapLine("  Reasoning: "+r.PlanStatus, width))
		b.WriteString("\n")
		if r.CurrentSituation != "" {
			b.WriteString(textutil.WrapLine("  Situation: "+r.CurrentSituation, width))
			b.WriteString("\n")
		}
		for i, step := range r.ReasoningSteps {
			b.WriteString(textutil.WrapLine(fmt.Sprintf("  %d. %s", i+1, step), width))
			b.WriteString("\n")
		}
	}

	for _, tool := range entry.Tools {
		icon := "○"
		switch tool.Status {
		case "done":
			icon = "✓"
		case "error":
			icon = "✗"
		case "started":
			icon = "…"
		}
		b.WriteString(textutil.WrapLine(fmt.Sprintf("  %s %s", icon, tool.Name), width))
		b.WriteString("\n")
	}

	for _, turn := range entry.Turns {
		b.WriteString(jsonfmt.FormatMessage(turn, width))
		b.WriteString("\n")
	}

	if entry.Buffer != "" {
		text := entry.Buffer
		if entry.Streaming {
			text += "▍"
		}
		b.WriteString(jsonfmt.FormatMessage(text, width))
		b.WriteString("\n")
	}

	return b.String()
}
