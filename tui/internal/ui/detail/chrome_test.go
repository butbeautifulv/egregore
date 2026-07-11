package detail

import (
	"testing"
)

func TestFollowUpComposerPanelLines(t *testing.T) {
	if followUpComposerPanelLines() < followUpComposerLines {
		t.Fatalf("panel lines too small")
	}
}
