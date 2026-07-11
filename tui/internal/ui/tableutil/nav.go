package tableutil

import (
	"github.com/charmbracelet/bubbles/key"
	"github.com/charmbracelet/bubbles/table"
	tea "github.com/charmbracelet/bubbletea"
)

// UpdateWrap forwards navigation keys to the table with wrap-around at the ends.
func UpdateWrap(t table.Model, msg tea.Msg, rowCount int) (table.Model, tea.Cmd) {
	if rowCount <= 1 {
		return t.Update(msg)
	}
	keyMsg, ok := msg.(tea.KeyMsg)
	if !ok {
		return t.Update(msg)
	}

	last := rowCount - 1
	cursor := t.Cursor()
	km := t.KeyMap

	switch {
	case key.Matches(keyMsg, km.LineUp):
		if cursor <= 0 {
			t.SetCursor(last)
			return t, nil
		}
	case key.Matches(keyMsg, km.LineDown):
		if cursor >= last {
			t.SetCursor(0)
			return t, nil
		}
	case key.Matches(keyMsg, km.PageUp), key.Matches(keyMsg, km.HalfPageUp):
		if cursor <= 0 {
			t.GotoBottom()
			return t, nil
		}
	case key.Matches(keyMsg, km.PageDown), key.Matches(keyMsg, km.HalfPageDown):
		if cursor >= last {
			t.GotoTop()
			return t, nil
		}
	}

	return t.Update(msg)
}
