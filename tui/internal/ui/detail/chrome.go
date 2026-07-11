package detail

// ChromeBudget tracks fixed lines consumed above the scroll viewport.
type ChromeBudget struct {
	Tabs     int
	Err      int
	Loading  int
	Composer int
}

func (b ChromeBudget) Total() int {
	return b.Tabs + b.Err + b.Loading + b.Composer
}

func (m Model) chromeBudget() ChromeBudget {
	b := ChromeBudget{Tabs: 1}
	if m.err != "" {
		b.Err = 1
	}
	if m.loading {
		b.Loading = 1
	}
	if m.showFollowUpComposer() {
		b.Composer = followUpComposerPanelLines()
	}
	return b
}

func (m Model) showFollowUpComposer() bool {
	return m.tab == TabChat && m.workOrderID != ""
}

func followUpComposerPanelLines() int {
	// panel border (2) + hint line + textarea block
	return followUpComposerLines + 3
}
