package layout

import "testing"

func TestOperatorConsoleLayoutSplit(t *testing.T) {
	pl := OperatorConsolePaneLayout(120, 40, DefaultLeftPanelRatio)

	if pl.Footer.Height != 1 {
		t.Fatalf("footer height: got %d want 1", pl.Footer.Height)
	}
	if pl.Footer.Y != 39 {
		t.Fatalf("footer y: got %d want 39", pl.Footer.Y)
	}
	sum := pl.Left.Width + pl.Separator.Width + pl.Right.Width
	if sum != 120 {
		t.Fatalf("width sum: got %d want 120", sum)
	}
	if pl.Left.Width < 55 || pl.Left.Width > 65 {
		t.Fatalf("left width ~60: got %d", pl.Left.Width)
	}
	if pl.Left.Height != 39 {
		t.Fatalf("left height: got %d want 39", pl.Left.Height)
	}
	if pl.Separator.Width != 1 {
		t.Fatalf("separator width: got %d want 1", pl.Separator.Width)
	}
}

func TestOperatorConsoleLayoutLimit(t *testing.T) {
	pl := OperatorConsolePaneLayout(8, 8, DefaultLeftPanelRatio)
	if pl.Mode != ModeLimit {
		t.Fatalf("mode %q want limit", pl.Mode)
	}
	if pl.Limit.Width != 8 || pl.Limit.Height != 8 {
		t.Fatalf("limit dims: %+v", pl.Limit)
	}
}

func TestOperatorConsoleLayoutMinClamp(t *testing.T) {
	pl := OperatorConsolePaneLayout(10, 9, DefaultLeftPanelRatio)
	if pl.Left.Width < 1 || pl.Right.Width < 1 {
		t.Fatalf("panels should have positive width: left=%d right=%d", pl.Left.Width, pl.Right.Width)
	}
	if pl.Footer.Height != 1 {
		t.Fatalf("footer height: got %d", pl.Footer.Height)
	}
}

func TestArrangeFixedSize(t *testing.T) {
	root := &Box{
		Direction: Column,
		Children: []*Box{
			{Window: "main", Weight: 1},
			{Window: "footer", Size: 2},
		},
	}
	dims := Arrange(root, 0, 0, 80, 20)
	if dims["footer"].Height != 2 {
		t.Fatalf("footer height: got %d want 2", dims["footer"].Height)
	}
	if dims["main"].Height != 18 {
		t.Fatalf("main height: got %d want 18", dims["main"].Height)
	}
}
