package detail

import (
	"fmt"
	"strings"

	"github.com/butbeautifulv/egregore/tui/internal/api"
	"github.com/butbeautifulv/egregore/tui/internal/style"
	"github.com/butbeautifulv/egregore/tui/internal/textutil"
	"github.com/butbeautifulv/egregore/tui/internal/ui/fit"
)

const followUpComposerLines = 3

// CanComposeFollowUp matches backend: follow-ups only on closed work orders.
func CanComposeFollowUp(detail *api.InvestigationDetail) bool {
	return detail != nil && detail.Status == "closed"
}

func (m Model) renderFollowUpComposerPanel() string {
	if m.tab != TabChat {
		return ""
	}
	innerW := max(10, m.width-4)
	if !CanComposeFollowUp(m.detail) {
		return fit.ClipLine(m.width, style.HelpStyle().Render(
			"Follow-ups available when the work order is closed.",
		))
	}
	var body strings.Builder
	hint := "Follow-up · Ctrl+Enter send · Esc scroll · m edit"
	if m.sendingFollow {
		hint = "Sending follow-up…"
	}
	body.WriteString(style.HelpStyle().Render(hint))
	body.WriteString("\n")
	if m.composerEditing {
		body.WriteString(m.composer.View())
	} else {
		body.WriteString(style.HelpStyle().Render("Press m to write a follow-up…"))
	}
	return style.PanelStyle().
		Width(innerW).
		MaxWidth(innerW).
		Render(body.String())
}

func renderFollowUpHistory(turns []api.FollowUpTurn, width int) string {
	if len(turns) == 0 {
		return "No follow-up turns yet."
	}
	var b strings.Builder
	for _, turn := range turns {
		label := turn.Role
		if turn.Role == "assistant" && turn.Persona != nil && *turn.Persona != "" {
			label = *turn.Persona
		}
		b.WriteString(textutil.WrapLine(fmt.Sprintf("[%s] %s", label, turn.Text), width))
		b.WriteString("\n")
	}
	return b.String()
}
