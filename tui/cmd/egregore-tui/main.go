package main

import (
	"fmt"
	"os"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/butbeautifulv/egregore/tui/internal/config"
	"github.com/butbeautifulv/egregore/tui/internal/ui"
	"github.com/butbeautifulv/egregore/tui/internal/ui/sse"
)

func main() {
	cfg := config.Load()
	model := ui.NewModel(cfg)
	p := tea.NewProgram(model, tea.WithAltScreen())
	sse.SetDefault(p.Send)
	if _, err := p.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "egregore-tui: %v\n", err)
		os.Exit(1)
	}
}
