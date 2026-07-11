package tableutil

import "testing"

func TestLayoutDistributesWidth(t *testing.T) {
	specs := []ColumnSpec{
		{Title: "Goal", MinWidth: 20, Weight: 3},
		{Title: "Status", MinWidth: 10, Weight: 0},
		{Title: "Updated", MinWidth: 12, Weight: 0},
		{Title: "Personas", MinWidth: 10, Weight: 1},
	}
	cols := Layout(120, specs)
	total := 0
	for _, c := range cols {
		if c.Width < minColWidth {
			t.Fatalf("invalid width for %s", c.Title)
		}
		total += c.Width
	}
	if total != 120 {
		t.Fatalf("columns should fill terminal: %d != 120", total)
	}
}

func TestLayoutFitsNarrowTerminal(t *testing.T) {
	specs := []ColumnSpec{
		{Title: "Goal", MinWidth: 20, Weight: 3},
		{Title: "Status", MinWidth: 10, Weight: 0},
		{Title: "Updated", MinWidth: 14, Weight: 0},
		{Title: "Personas", MinWidth: 10, Weight: 1},
	}
	for _, width := range []int{52, 60, 72, 80} {
		cols := Layout(width, specs)
		total := 0
		for _, c := range cols {
			total += c.Width
		}
		if total > width {
			t.Fatalf("width %d: columns wider than terminal: %d", width, total)
		}
		if total < width {
			t.Fatalf("width %d: unused space: %d", width, total)
		}
	}
}
