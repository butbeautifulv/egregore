package panels

import (
	"fmt"
	"strings"

	"github.com/butbeautifulv/egregore/tui/internal/style"
	"github.com/butbeautifulv/egregore/tui/internal/ui/components"
	"github.com/butbeautifulv/egregore/tui/internal/ui/fit"
)

const sectionBorderOverhead = 2 // top + bottom border lines

// Section is a framed list widget for the left panel.
type Section struct {
	Name             string
	Key              string // section hotkey shown in title, e.g. "1"
	Items            []string
	Cursor           int
	Height           int
	Width            int
	Focused          bool
	Active           bool // expanded accordion section
	Collapsed        bool // collapsed to title-only
	CollapsedSummary string
	Badge            int
	HeaderLines      []string
	Extra            string
}

// View renders the section with border frame clipped to Width×Height.
func (s Section) View() string {
	if s.Collapsed {
		return s.collapsedView()
	}
	return s.framedView()
}

func (s Section) collapsedView() string {
	if s.Width <= 0 {
		s.Width = 40
	}
	title := s.Name
	if s.Key != "" {
		title = s.Key + " " + s.Name
	}
	if s.Badge > 0 {
		title += " [" + itoa(s.Badge) + "]"
	}
	line := title
	if s.CollapsedSummary != "" {
		line += "  " + s.CollapsedSummary
	}
	out := fit.PadLine(s.Width, components.RenderSectionTitle(line, s.Width))
	return fit.FitBlock(s.Width, 1, out)
}

func (s Section) framedView() string {
	w := s.Width
	if w <= 0 {
		w = 40
	}
	h := s.Height
	if h < sectionBorderOverhead+1 {
		h = sectionBorderOverhead + 1
	}

	innerW := w - 1 // left │ takes one column; open on the right
	if innerW < 1 {
		innerW = 1
	}
	innerH := h - sectionBorderOverhead
	if innerH < 1 {
		innerH = 1
	}

	body := s.renderBody(innerW, innerH)
	if s.Extra != "" {
		body = body + "\n" + fit.ClipLine(innerW, s.Extra)
		body = fit.ClipBlock(innerW, innerH, body)
	}

	bodyLines := strings.Split(body, "\n")
	for len(bodyLines) < innerH {
		bodyLines = append(bodyLines, "")
	}
	if len(bodyLines) > innerH {
		bodyLines = bodyLines[:innerH]
	}

	frame := style.SectionFrameStyle(s.Focused && s.Active)
	lines := make([]string, 0, h)
	lines = append(lines, fit.PadLine(w, frame.Render("┌"+strings.Repeat("─", w-1))))
	for _, row := range bodyLines {
		lines = append(lines, frame.Render("│")+fit.PadLine(w-1, row))
	}
	lines = append(lines, fit.PadLine(w, frame.Render("└"+strings.Repeat("─", w-1))))

	return fit.FitBlock(w, h, strings.Join(lines, "\n"))
}

func (s Section) renderBody(innerW, innerH int) string {
	title := s.titleLine(innerW)

	var b strings.Builder
	b.WriteString(fit.ClipLine(innerW, title))

	maxLines := innerH - 1
	if s.Extra != "" && maxLines > 1 {
		maxLines--
	}
	for _, hl := range s.HeaderLines {
		if maxLines <= 0 {
			break
		}
		b.WriteString("\n")
		b.WriteString(fit.ClipLine(innerW, hl))
		maxLines--
	}
	if maxLines < 1 {
		return b.String()
	}

	if len(s.Items) == 0 {
		b.WriteString("\n")
		b.WriteString(fit.ClipLine(innerW, style.HelpStyle().Render("  (empty)")))
		return b.String()
	}

	start := 0
	if s.Cursor >= maxLines {
		start = s.Cursor - maxLines + 1
	}
	end := start + maxLines
	if end > len(s.Items) {
		end = len(s.Items)
	}
	for i := start; i < end; i++ {
		line := s.Items[i]
		if i == s.Cursor && s.Focused {
			line = style.SelectedRowStyle().Render("> " + strings.TrimPrefix(line, "> "))
		} else {
			line = "  " + strings.TrimPrefix(strings.TrimPrefix(line, "> "), "  ")
		}
		b.WriteString("\n")
		b.WriteString(fit.ClipLine(innerW, line))
	}
	return b.String()
}

func (s Section) titleLine(innerW int) string {
	title := s.Name
	if s.Key != "" {
		title = s.Key + " " + s.Name
	}
	if s.Badge > 0 {
		title += " [" + itoa(s.Badge) + "]"
	}
	if len(s.Items) > 0 {
		maxLines := s.Height - sectionBorderOverhead - 1
		if maxLines < 1 {
			maxLines = 1
		}
		if len(s.Items) > maxLines {
			pos := s.Cursor + 1
			if pos > len(s.Items) {
				pos = len(s.Items)
			}
			title += fmt.Sprintf(" (%d/%d)", pos, len(s.Items))
		}
	}
	return components.RenderSectionTitle(title, innerW)
}

// MoveCursor moves selection by delta and clamps.
func (s *Section) MoveCursor(delta int) {
	if len(s.Items) == 0 {
		s.Cursor = 0
		return
	}
	s.Cursor += delta
	s.ClampCursor()
}

// ClampCursor keeps cursor in range.
func (s *Section) ClampCursor() {
	if len(s.Items) == 0 {
		s.Cursor = 0
		return
	}
	if s.Cursor < 0 {
		s.Cursor = 0
	}
	if s.Cursor >= len(s.Items) {
		s.Cursor = len(s.Items) - 1
	}
}

// JumpTop moves cursor to first item.
func (s *Section) JumpTop() {
	s.Cursor = 0
}

// JumpBottom moves cursor to last item.
func (s *Section) JumpBottom() {
	if len(s.Items) > 0 {
		s.Cursor = len(s.Items) - 1
	}
}

// VisibleLines returns how many item lines fit in the section body.
func (s Section) VisibleLines() int {
	if s.Collapsed {
		return 1
	}
	innerH := s.Height - sectionBorderOverhead
	if innerH <= 1 {
		return 1
	}
	n := innerH - 1
	n -= len(s.HeaderLines)
	if s.Extra != "" {
		n--
	}
	if n < 1 {
		return 1
	}
	return n
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var digits []byte
	for n > 0 {
		digits = append([]byte{byte('0' + n%10)}, digits...)
		n /= 10
	}
	return string(digits)
}
