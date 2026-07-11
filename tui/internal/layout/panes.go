package layout

const (
	WindowSeparator = "separator"
	WindowLimit     = "limit"

	minTerminalWidth  = 10
	minTerminalHeight = 9
)

// Mode describes responsive layout degradation.
type Mode string

const (
	ModeNormal   Mode = "normal"
	ModeCompact  Mode = "compact"
	ModeLimit    Mode = "limit"
	ModePortrait Mode = "portrait"
)

// PaneLayout is the single source of truth for operator console geometry.
type PaneLayout struct {
	Mode      Mode
	Left      Dimensions
	Separator Dimensions
	Right     Dimensions
	Footer    Dimensions
	Limit     Dimensions
}

// OperatorConsolePaneLayout computes pane regions for the given terminal size.
func OperatorConsolePaneLayout(width, height int, leftRatio float64) PaneLayout {
	if width < minTerminalWidth || height < minTerminalHeight {
		dims := Arrange(&Box{Window: WindowLimit}, 0, 0, maxInt(1, width), maxInt(1, height))
		return PaneLayout{Mode: ModeLimit, Limit: dims[WindowLimit]}
	}

	mode := ModeNormal
	if height < 12 {
		mode = ModeCompact
	}

	portrait := width <= 84 && height > 20 && height <= 45
	if leftRatio <= 0 || leftRatio >= 1 {
		leftRatio = DefaultLeftPanelRatio
	}
	leftWeight := int(leftRatio * 1000)
	rightWeight := 1000 - leftWeight
	if leftWeight < 1 {
		leftWeight = 1
	}
	if rightWeight < 1 {
		rightWeight = 1
	}

	var root *Box
	if portrait {
		mode = ModePortrait
		root = &Box{
			Direction: Column,
			Children: []*Box{
				{Window: WindowLeft, Weight: 1},
				{Window: WindowRight, Weight: 1},
				{Window: WindowFooter, Size: 1},
			},
		}
	} else {
		root = &Box{
			Direction: Column,
			Children: []*Box{
				{
					Direction: Row,
					Weight:    1,
					Children: []*Box{
						{Window: WindowLeft, Weight: leftWeight},
						{Window: WindowSeparator, Size: 1},
						{Window: WindowRight, Weight: rightWeight},
					},
				},
				{Window: WindowFooter, Size: 1},
			},
		}
	}

	dims := Arrange(root, 0, 0, width, height)
	pl := PaneLayout{
		Mode:   mode,
		Left:   dims[WindowLeft],
		Right:  dims[WindowRight],
		Footer: dims[WindowFooter],
	}
	if sep, ok := dims[WindowSeparator]; ok {
		pl.Separator = sep
	}
	return pl
}

// RightInnerSize returns content area inside the right pane frame (open left).
func (pl PaneLayout) RightInnerSize() (width, height int) {
	width = maxInt(1, pl.Right.Width-1)
	height = maxInt(1, pl.Right.Height-2)
	return width, height
}

// LeftInnerSize returns the left stack content width and height.
func (pl PaneLayout) LeftInnerSize() (width, height int) {
	return maxInt(1, pl.Left.Width), maxInt(1, pl.Left.Height)
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}
