package chat

import (
	"fmt"
	"sort"
	"strings"

	"github.com/butbeautifulv/egregore/tui/internal/api"
	"github.com/butbeautifulv/egregore/tui/internal/jsonfmt"
	"github.com/butbeautifulv/egregore/tui/internal/style"
	"github.com/butbeautifulv/egregore/tui/internal/textutil"
)

// FollowUpPair groups operator and assistant turns for one follow-up id.
type FollowUpPair struct {
	FollowUpID string
	Operator   api.FollowUpTurn
	Assistant  *api.FollowUpTurn
}

// GroupFollowUpPairs groups turns by follow_up_id (mirrors web groupFollowUpPairs).
func GroupFollowUpPairs(turns []api.FollowUpTurn) []FollowUpPair {
	byID := make(map[string]*FollowUpPair)
	for _, turn := range turns {
		id := turn.FollowUpID
		if id == "" {
			id = turn.ID
		}
		existing, ok := byID[id]
		if !ok {
			pair := &FollowUpPair{FollowUpID: id}
			if turn.Role == "operator" {
				pair.Operator = turn
			} else {
				pair.Operator = api.FollowUpTurn{
					ID:         "placeholder-" + id,
					Role:       "operator",
					FollowUpID: id,
					CreatedAt:  turn.CreatedAt,
				}
				t := turn
				pair.Assistant = &t
			}
			byID[id] = pair
			continue
		}
		if turn.Role == "operator" {
			existing.Operator = turn
		} else {
			t := turn
			existing.Assistant = &t
		}
	}
	out := make([]FollowUpPair, 0, len(byID))
	for _, p := range byID {
		out = append(out, *p)
	}
	sort.Slice(out, func(i, j int) bool {
		return out[i].Operator.CreatedAt < out[j].Operator.CreatedAt
	})
	return out
}

// RenderFollowUpPairs renders grouped follow-up Q/A blocks for the chat timeline.
func RenderFollowUpPairs(pairs []FollowUpPair, width int) string {
	if len(pairs) == 0 {
		return ""
	}
	if width < 10 {
		width = 10
	}
	var b strings.Builder
	for _, pair := range pairs {
		label := followUpMarkerLabel(pair)
		b.WriteString(style.SectionTitleStyle().Render(textutil.Truncate(label, width)))
		b.WriteString("\n")
		if strings.TrimSpace(pair.Operator.Text) != "" {
			b.WriteString(textutil.WrapLine("[operator] "+pair.Operator.Text, width))
			b.WriteString("\n")
		}
		if pair.Assistant != nil {
			role := pair.Assistant.Role
			if pair.Assistant.Persona != nil && *pair.Assistant.Persona != "" {
				role = *pair.Assistant.Persona
			}
			b.WriteString(textutil.WrapLine("["+role+"] "+pair.Assistant.Text, width))
			b.WriteString("\n")
		}
		b.WriteString("\n")
	}
	return b.String()
}

func followUpMarkerLabel(pair FollowUpPair) string {
	if pair.Assistant != nil && pair.Assistant.Persona != nil && *pair.Assistant.Persona != "" {
		return "─── Follow-up · " + *pair.Assistant.Persona + " ───"
	}
	return "─── Follow-up ───"
}

// RenderChat produces scrollable text for the chat viewport.
func RenderChat(
	detail *api.InvestigationDetail,
	state *State,
	jobs []api.JobSummary,
	followUps []api.FollowUpTurn,
	opts RenderOptions,
) string {
	if detail == nil {
		return ""
	}
	width := opts.Width
	if width < 10 {
		width = 10
	}

	var b strings.Builder
	b.WriteString(textutil.WrapLine("Goal: "+detail.Goal, width))
	b.WriteString("\n")
	b.WriteString(textutil.WrapLine(fmt.Sprintf("Status: %s  ID: %s", detail.Status, detail.InvestigationID), width))
	b.WriteString("\n\n")

	plannerID := PlannerJobID(detail.InvestigationID)
	entries := SortEntries(state.Entries(), plannerID, detail.PlannerPlan, jobs)

	for _, entry := range entries {
		b.WriteString(renderEntry(entry, opts, width))
		b.WriteString("\n")
	}

	if detail.FinalReport != nil && len(detail.FinalReport) > 0 {
		b.WriteString("\n--- Final Report ---\n")
		b.WriteString(textutil.WrapBlock(jsonfmt.FormatValue(detail.FinalReport), width))
		b.WriteString("\n")
	}

	if pairs := GroupFollowUpPairs(followUps); len(pairs) > 0 {
		b.WriteString("\n")
		b.WriteString(RenderFollowUpPairs(pairs, width))
	}

	return b.String()
}
