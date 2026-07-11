package console

const collapsedSectionHeight = 1

// visibleLeftSections returns sections shown in the left stack.
func visibleLeftSections(showQueues bool) []LeftSection {
	if showQueues {
		return []LeftSection{
			SectionStatus,
			SectionApprovals,
			SectionQueues,
			SectionCatalog,
			SectionWorkOrders,
		}
	}
	return []LeftSection{
		SectionStatus,
		SectionApprovals,
		SectionCatalog,
		SectionWorkOrders,
	}
}

// sectionHeights allocates vertical space using accordion layout.
// Inactive sections get one plain title line; active section gets the remainder
// (including its border frame). Sum of heights equals total.
func sectionHeights(total int, active LeftSection, showQueues bool) map[LeftSection]int {
	sections := visibleLeftSections(showQueues)
	out := make(map[LeftSection]int, len(sections))
	if total <= 0 {
		return out
	}

	n := len(sections)
	if total < n {
		for i, sec := range sections {
			if i == len(sections)-1 {
				out[sec] = total - i
			} else {
				out[sec] = 1
			}
		}
		return out
	}

	inactive := n - 1
	collapsedTotal := inactive * collapsedSectionHeight
	expanded := total - collapsedTotal
	minExpanded := 5
	if expanded < minExpanded {
		expanded = minExpanded
	}

	for _, sec := range sections {
		if sec == active {
			out[sec] = expanded
		} else {
			out[sec] = collapsedSectionHeight
		}
	}

	sum := 0
	for _, sec := range sections {
		sum += out[sec]
	}
	switch {
	case sum > total:
		out[active] -= sum - total
		if out[active] < minExpanded && total >= minExpanded+(inactive*collapsedSectionHeight) {
			out[active] = minExpanded
		}
		if out[active] < 3 {
			out[active] = total - inactive*collapsedSectionHeight
			if out[active] < 3 {
				out[active] = 3
			}
		}
	case sum < total:
		out[active] += total - sum
	}
	return out
}

func sumSectionHeights(heights map[LeftSection]int, sections []LeftSection) int {
	total := 0
	for _, sec := range sections {
		total += heights[sec]
	}
	return total
}
