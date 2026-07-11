package panels

import (
	"strings"
	"testing"

	"github.com/charmbracelet/lipgloss"
)

func TestSectionViewHighlightsCursor(t *testing.T) {
	s := Section{
		Name:    "Test",
		Items:   []string{"one", "two", "three"},
		Cursor:  1,
		Height:  5,
		Width:   30,
		Focused: true,
		Active:  true,
	}
	out := s.View()
	if !strings.Contains(out, "two") {
		t.Fatalf("missing item: %q", out)
	}
}

func TestSectionCollapsedShowsText(t *testing.T) {
	s := Section{
		Name:             "Status",
		Key:              "1",
		Height:           1,
		Width:            40,
		Collapsed:        true,
		CollapsedSummary: "api ok",
	}
	out := s.View()
	if strings.TrimSpace(out) == "" {
		t.Fatalf("collapsed section empty")
	}
	if !strings.Contains(out, "Status") {
		t.Fatalf("missing title: %q", out)
	}
	if lipgloss.Height(out) != 1 {
		t.Fatalf("collapsed height: got %d want 1", lipgloss.Height(out))
	}
}

func TestSectionFramedWithinHeight(t *testing.T) {
	s := Section{
		Name:   "Work orders",
		Key:    "5",
		Items:  []string{"a", "b", "c", "d", "e", "f"},
		Cursor: 3,
		Height: 6,
		Width:  40,
		Active: true,
	}
	out := s.View()
	if lipgloss.Height(out) != s.Height {
		t.Fatalf("height %d want %d", lipgloss.Height(out), s.Height)
	}
	for i, line := range strings.Split(out, "\n") {
		if lipgloss.Width(line) > s.Width {
			t.Fatalf("line %d width %d exceeds %d: %q", i, lipgloss.Width(line), s.Width, line)
		}
	}
}

func TestSectionScrollIndicator(t *testing.T) {
	s := Section{
		Name:   "Work orders",
		Key:    "5",
		Items:  []string{"1", "2", "3", "4", "5", "6"},
		Cursor: 2,
		Height: 5,
		Width:  40,
		Active: true,
	}
	out := s.View()
	if !strings.Contains(out, "(3/6)") {
		t.Fatalf("missing scroll indicator: %q", out)
	}
}

func TestSectionMoveCursor(t *testing.T) {
	s := Section{Items: []string{"a", "b"}}
	s.MoveCursor(5)
	if s.Cursor != 1 {
		t.Fatalf("cursor: got %d", s.Cursor)
	}
	s.JumpTop()
	if s.Cursor != 0 {
		t.Fatalf("top: got %d", s.Cursor)
	}
}
