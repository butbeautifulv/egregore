package fit

import (
	"strings"

	"github.com/charmbracelet/lipgloss"
)

// FrameRightPane draws top/right/bottom borders; the left edge is the shared separator.
func FrameRightPane(width, height int, inner string, border lipgloss.Style) string {
	if width <= 0 || height <= 0 {
		return ""
	}
	if height < 2 {
		height = 2
	}
	innerW := width - 1
	innerH := height - 2
	if innerW < 1 {
		innerW = 1
	}
	if innerH < 1 {
		innerH = 1
	}

	innerLines := strings.Split(FitBlock(innerW, innerH, inner), "\n")
	lines := make([]string, height)
	lines[0] = PadLine(width, border.Render(strings.Repeat("─", innerW)+"┐"))
	for i := 0; i < innerH; i++ {
		row := ""
		if i < len(innerLines) {
			row = innerLines[i]
		}
		lines[i+1] = PadLine(innerW, row) + border.Render("│")
	}
	lines[height-1] = PadLine(width, border.Render(strings.Repeat("─", innerW)+"┘"))
	return FitBlock(width, height, strings.Join(lines, "\n"))
}

// JoinOperatorPanes places left content, a 1-column separator, and a framed right pane.
func JoinOperatorPanes(leftW, sepW, rightW, height int, leftInner, rightInner string, sepBorder, rightBorder lipgloss.Style) string {
	if height <= 0 {
		return ""
	}
	if leftW < 1 {
		leftW = 1
	}
	if sepW < 1 {
		sepW = 1
	}
	if rightW < 1 {
		rightW = 1
	}

	leftLines := strings.Split(FitBlock(leftW, height, leftInner), "\n")
	rightFramed := FrameRightPane(rightW, height, rightInner, rightBorder)
	rightLines := strings.Split(FitBlock(rightW, height, rightFramed), "\n")

	sep := sepBorder.Render("│")
	out := make([]string, height)
	for i := 0; i < height; i++ {
		l := ""
		r := ""
		if i < len(leftLines) {
			l = leftLines[i]
		}
		if i < len(rightLines) {
			r = rightLines[i]
		}
		out[i] = PadLine(leftW, l) + PadLine(sepW, sep) + PadLine(rightW, r)
	}
	return strings.Join(out, "\n")
}

// JoinPortraitPanes stacks left over right for narrow portrait layout.
func JoinPortraitPanes(width, topH, bottomH int, topInner, bottomInner string, bottomBorder lipgloss.Style) string {
	if topH < 0 {
		topH = 0
	}
	if bottomH < 0 {
		bottomH = 0
	}
	top := FitBlock(width, topH, topInner)
	bottomFramed := FrameRightPane(width, bottomH, bottomInner, bottomBorder)
	bottom := FitBlock(width, bottomH, bottomFramed)
	if topH == 0 {
		return bottom
	}
	if bottomH == 0 {
		return top
	}
	return top + "\n" + bottom
}
