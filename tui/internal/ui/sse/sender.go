package sse

import tea "github.com/charmbracelet/bubbletea"

// Sender delivers messages from background goroutines into the Bubble Tea program.
type Sender func(tea.Msg)

var defaultSender Sender

// SetDefault configures the global SSE message sender.
func SetDefault(s Sender) {
	defaultSender = s
}

// Send dispatches a message if a sender is configured.
func Send(msg tea.Msg) {
	if defaultSender != nil {
		defaultSender(msg)
	}
}
