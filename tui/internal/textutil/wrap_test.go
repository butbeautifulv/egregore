package textutil

import (
	"strings"
	"testing"

	"github.com/mattn/go-runewidth"
)

func TestWrapBlockCyrillic(t *testing.T) {
	text := "Пользователь поприветствовал систему без указания цели"
	wrapped := WrapBlock(text, 20)
	for _, line := range strings.Split(wrapped, "\n") {
		if strings.Contains(line, "\ufffd") {
			t.Fatalf("replacement char in line: %q", line)
		}
		if runewidth.StringWidth(line) > 20 {
			t.Fatalf("line too wide (%d): %q", runewidth.StringWidth(line), line)
		}
	}
}

func TestTruncateCyrillic(t *testing.T) {
	s := "расследование"
	out := Truncate(s, 8)
	if strings.Contains(out, "\ufffd") {
		t.Fatalf("broken utf8: %q", out)
	}
}
