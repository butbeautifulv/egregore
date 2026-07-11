package console

import (
	"fmt"

	"github.com/butbeautifulv/egregore/tui/internal/ui/components"
	"github.com/butbeautifulv/egregore/tui/internal/ui/detail"
)

// KeybarBindings returns footer hotkeys for the current UI state.
func KeybarBindings(
	focus FocusArea,
	section LeftSection,
	tab detail.Tab,
	overlayOpen bool,
	inputActive bool,
) map[string]string {
	if overlayOpen {
		return map[string]string{
			"Ctrl+Enter": "submit",
			"Esc":        "cancel",
		}
	}
	if inputActive {
		return map[string]string{
			"Ctrl+Enter": "send",
			"Esc":        "cancel",
		}
	}
	b := map[string]string{
		"Tab": "focus",
		"q":   "quit",
		"?":   "help",
	}
	if focus == FocusLeft {
		b["1-5"] = "section"
		b["[/]"] = "prev/next"
		b["↑↓"] = "select"
		b["r"] = "refresh"
		switch section {
		case SectionWorkOrders:
			b["n"] = "new"
			b["Enter"] = "open"
			b["g/G"] = "jump"
		case SectionApprovals:
			b["a/x"] = "HITL"
			b["Enter"] = "open WO"
		case SectionCatalog:
			b["a/s/m/t/p"] = "catalog"
			b["←→"] = "catalog tab"
			b["Enter"] = "detail"
			b["/"] = "filter mem"
		}
	} else {
		b["←→"] = "tabs"
		b["PgUp/Dn"] = "scroll"
		switch tab {
		case detail.TabChat:
			b["a/x"] = "HITL"
			b["r"] = "reasoning"
			b["m"] = "follow-up"
			b["Ctrl+Enter"] = "send"
		}
		b["Esc"] = "back"
	}
	return b
}

// RenderKeybar builds the footer line.
func RenderKeybar(
	focus FocusArea,
	section LeftSection,
	tab detail.Tab,
	apiURL, tenant string,
	width int,
	overlayOpen, inputActive bool,
) string {
	bindings := KeybarBindings(focus, section, tab, overlayOpen, inputActive)
	right := fmt.Sprintf("API: %s  tenant: %s", apiURL, tenant)
	return components.RenderKeybar(bindings, right, width)
}
