package console

import "testing"

func TestSectionHeightsSumEqualsTotal(t *testing.T) {
	cases := []struct {
		total      int
		active     LeftSection
		showQueues bool
	}{
		{24, SectionWorkOrders, true},
		{24, SectionCatalog, true},
		{12, SectionStatus, true},
		{8, SectionApprovals, false},
		{40, SectionQueues, true},
	}
	for _, tc := range cases {
		sections := visibleLeftSections(tc.showQueues)
		heights := sectionHeights(tc.total, tc.active, tc.showQueues)
		sum := sumSectionHeights(heights, sections)
		if sum != tc.total {
			t.Fatalf("total=%d active=%v showQueues=%v: sum=%d heights=%v",
				tc.total, tc.active, tc.showQueues, sum, heights)
		}
		if heights[tc.active] <= collapsedSectionHeight {
			t.Fatalf("active section should expand: got %d", heights[tc.active])
		}
	}
}

func TestSectionHeightsCollapsedInactive(t *testing.T) {
	heights := sectionHeights(20, SectionWorkOrders, true)
	sections := visibleLeftSections(true)
	for _, sec := range sections {
		if sec == SectionWorkOrders {
			continue
		}
		if heights[sec] != collapsedSectionHeight {
			t.Fatalf("section %v: got height %d want %d", sec, heights[sec], collapsedSectionHeight)
		}
	}
}
