package tableutil

import (
	"testing"

	"github.com/charmbracelet/bubbles/table"
	tea "github.com/charmbracelet/bubbletea"
)

func testTable(rows int) table.Model {
	tbl := table.New(table.WithFocused(true))
	tbl.SetColumns([]table.Column{{Title: "x", Width: 10}})
	data := make([]table.Row, rows)
	for i := range data {
		data[i] = table.Row{"row"}
	}
	tbl.SetRows(data)
	return tbl
}

func TestUpdateWrapCyclesDown(t *testing.T) {
	tbl := testTable(3)
	tbl.SetCursor(2)

	tbl, _ = UpdateWrap(tbl, tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'j'}}, 3)
	if tbl.Cursor() != 0 {
		t.Fatalf("expected wrap to top, got cursor %d", tbl.Cursor())
	}
}

func TestUpdateWrapCyclesUp(t *testing.T) {
	tbl := testTable(3)
	tbl.SetCursor(0)

	tbl, _ = UpdateWrap(tbl, tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'k'}}, 3)
	if tbl.Cursor() != 2 {
		t.Fatalf("expected wrap to bottom, got cursor %d", tbl.Cursor())
	}
}
