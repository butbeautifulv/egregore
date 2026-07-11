package layout

import "testing"

func TestOperatorConsolePaneLayoutCompact(t *testing.T) {
	pl := OperatorConsolePaneLayout(80, 10, DefaultLeftPanelRatio)
	if pl.Mode != ModeCompact {
		t.Fatalf("mode %q want compact", pl.Mode)
	}
	if pl.Footer.Height != 1 {
		t.Fatalf("footer height %d want 1", pl.Footer.Height)
	}
	sum := pl.Left.Width + pl.Separator.Width + pl.Right.Width
	if sum != 80 {
		t.Fatalf("width sum %d want 80", sum)
	}
}

func TestOperatorConsolePaneLayoutPortrait(t *testing.T) {
	pl := OperatorConsolePaneLayout(80, 30, DefaultLeftPanelRatio)
	if pl.Mode != ModePortrait {
		t.Fatalf("mode %q want portrait", pl.Mode)
	}
	if pl.Separator.Width != 0 {
		t.Fatalf("portrait should not allocate separator: %+v", pl.Separator)
	}
	if pl.Left.Width != 80 || pl.Right.Width != 80 {
		t.Fatalf("stacked panes should span full width: left=%d right=%d", pl.Left.Width, pl.Right.Width)
	}
}

func TestOperatorConsolePaneLayoutNormal(t *testing.T) {
	pl := OperatorConsolePaneLayout(120, 40, DefaultLeftPanelRatio)
	if pl.Mode != ModeNormal {
		t.Fatalf("mode %q want normal", pl.Mode)
	}
	if pl.Separator.Width != 1 {
		t.Fatalf("separator width %d want 1", pl.Separator.Width)
	}
}
