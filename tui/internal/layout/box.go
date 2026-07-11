package layout

// Flex box layout (inspired by lazycore boxlayout).

type Direction int

const (
	Row Direction = iota
	Column
)

// Dimensions describes a window region.
type Dimensions struct {
	X, Y, Width, Height int
}

// Box is a node in the layout tree.
type Box struct {
	Direction Direction
	Weight    int
	Size      int // fixed size along parent direction; 0 = flex
	Window    string
	Children  []*Box
}

// Arrange computes window dimensions for the tree rooted at root.
func Arrange(root *Box, x, y, width, height int) map[string]Dimensions {
	out := make(map[string]Dimensions)
	arrangeBox(root, x, y, width, height, out)
	return out
}

func arrangeBox(b *Box, x, y, width, height int, out map[string]Dimensions) {
	if b == nil {
		return
	}
	if b.Window != "" {
		out[b.Window] = Dimensions{X: x, Y: y, Width: width, Height: height}
	}
	if len(b.Children) == 0 {
		return
	}

	if b.Direction == Row {
		splitFlex(x, y, width, height, b.Children, true, out)
	} else {
		splitFlex(x, y, width, height, b.Children, false, out)
	}
}

func splitFlex(x, y, w, h int, children []*Box, horizontal bool, out map[string]Dimensions) {
	if len(children) == 0 {
		return
	}

	fixed := 0
	flexWeight := 0
	for _, c := range children {
		if c.Size > 0 {
			fixed += c.Size
		} else {
			weight := c.Weight
			if weight <= 0 {
				weight = 1
			}
			flexWeight += weight
		}
	}

	main := w
	if !horizontal {
		main = h
	}
	remaining := main - fixed
	if remaining < 0 {
		remaining = 0
	}

	pos := 0
	if horizontal {
		pos = x
	} else {
		pos = y
	}

	for _, c := range children {
		size := c.Size
		if size <= 0 {
			weight := c.Weight
			if weight <= 0 {
				weight = 1
			}
			size = 0
			if flexWeight > 0 {
				size = remaining * weight / flexWeight
			}
		}
		if size < 1 && c.Size <= 0 {
			size = 1
		}

		var cx, cy, cw, ch int
		if horizontal {
			cx, cy, cw, ch = pos, y, size, h
			pos += size
		} else {
			cx, cy, cw, ch = x, pos, w, size
			pos += size
		}
		arrangeBox(c, cx, cy, cw, ch, out)
	}

	// Distribute rounding remainder to flex children (lazydocker boxlayout pattern).
	if horizontal {
		if gap := w - (pos - x); gap > 0 {
			distributeRemainder(gap, children, out, true, x, y, h)
		}
	} else if gap := h - (pos - y); gap > 0 {
		distributeRemainder(gap, children, out, false, x, y, w)
	}
}

func distributeRemainder(gap int, children []*Box, out map[string]Dimensions, horizontal bool, x, y, cross int) {
	if len(children) == 0 || gap <= 0 {
		return
	}
	idx := 0
	for gap > 0 {
		c := children[idx%len(children)]
		if c.Window == "" {
			idx++
			continue
		}
		d := out[c.Window]
		if horizontal {
			d.Width++
		} else {
			d.Height++
		}
		out[c.Window] = d
		gap--
		idx++
	}
	_ = x
	_ = y
	_ = cross
}

const (
	WindowLeft   = "left"
	WindowRight  = "right"
	WindowFooter = "footer"

	// DefaultLeftPanelRatio is the default fraction of terminal width for the left stack.
	DefaultLeftPanelRatio = 0.50
)

// OperatorConsoleLayout returns left panel, right panel, and footer dimensions.
// Deprecated: prefer OperatorConsolePaneLayout for separator-aware layout.
func OperatorConsoleLayout(width, height int, leftRatio float64) (left, right, footer Dimensions) {
	pl := OperatorConsolePaneLayout(width, height, leftRatio)
	return pl.Left, pl.Right, pl.Footer
}
