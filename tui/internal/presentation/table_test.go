package presentation

import (
	"strings"
	"testing"
)

func TestRenderTableAlignsColoredStatus(t *testing.T) {
	green := "\x1b[32mrunning\x1b[0m"
	red := "\x1b[31mfailed\x1b[0m"
	rows := [][]string{
		{green, "api-service", "0.02%"},
		{red, "migrate", "0.00%"},
	}
	out := RenderTable(rows)
	lines := strings.Split(out, "\n")
	if len(lines) != 2 {
		t.Fatalf("lines: got %d", len(lines))
	}
	// Visible columns should align after status (8 chars)
	if !strings.HasSuffix(lines[0], "api-service 0.02%") && !strings.Contains(lines[0], "api-service") {
		t.Fatalf("row0: %q", lines[0])
	}
	// Both lines should have status ending at same visual column
	idx0 := strings.Index(lines[0], "api")
	idx1 := strings.Index(lines[1], "migrate")
	if idx0 != idx1 {
		t.Fatalf("column misaligned: %d vs %d\n%q\n%q", idx0, idx1, lines[0], lines[1])
	}
}

func TestDecolorise(t *testing.T) {
	s := "\x1b[32mok\x1b[0m"
	if Decolorise(s) != "ok" {
		t.Fatalf("got %q", Decolorise(s))
	}
}

func TestRenderTableSizedFitsWidth(t *testing.T) {
	rows := [][]string{
		{"Status", "Goal", "Updated"},
		{"running", strings.Repeat("x", 40), "2026-01-01"},
	}
	widths := []int{8, 12, 11}
	out := RenderTableSized(rows, widths)
	for _, line := range strings.Split(out, "\n") {
		w := 0
		for _, cell := range strings.Fields(line) {
			w += len(Decolorise(cell)) + 1
		}
		if len(line) > 35 {
			// row should not be excessively wide; goal truncated
			if strings.Contains(line, strings.Repeat("x", 30)) {
				t.Fatalf("goal not truncated: %q", line)
			}
		}
	}
}
