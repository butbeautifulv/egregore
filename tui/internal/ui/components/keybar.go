package components

import (
	"sort"
	"strings"

	"github.com/butbeautifulv/egregore/tui/internal/style"
	"github.com/butbeautifulv/egregore/tui/internal/textutil"
)

// RenderKeybar renders left key hints and right status text in one line.
func RenderKeybar(bindings map[string]string, right string, width int) string {
	if width <= 0 {
		width = 80
	}
	keys := make([]string, 0, len(bindings))
	for k := range bindings {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	var parts []string
	for _, k := range keys {
		parts = append(parts, k+": "+bindings[k])
	}
	left := strings.Join(parts, " · ")
	if right != "" {
		right = textutil.Truncate(right, width/3)
	}
	budget := width - len(right) - 2
	if budget < 0 {
		budget = 0
	}
	if len(left) > budget {
		left = textutil.Truncate(left, budget)
	}
	line := left
	if right != "" {
		if line != "" {
			line += "  "
		}
		line += right
	}
	return style.StatusBarStyle().Width(width).MaxWidth(width).Render(line)
}
