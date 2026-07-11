package console

// FocusArea is which pane has keyboard focus.
type FocusArea int

const (
	FocusLeft FocusArea = iota
	FocusRight
)

// LeftSection identifies a section in the left stack (display order = iota).
type LeftSection int

const (
	SectionStatus LeftSection = iota // key 1
	SectionApprovals                 // key 2
	SectionQueues                    // key 3
	SectionCatalog                   // key 4
	SectionWorkOrders                // key 5 — bottom
	sectionCount
)

func (s LeftSection) Name() string {
	switch s {
	case SectionStatus:
		return "Status"
	case SectionApprovals:
		return "Approvals"
	case SectionQueues:
		return "Queues"
	case SectionCatalog:
		return "Catalog"
	case SectionWorkOrders:
		return "Work orders"
	default:
		return ""
	}
}

func (s LeftSection) KeyHint() string {
	switch s {
	case SectionStatus:
		return "1"
	case SectionApprovals:
		return "2"
	case SectionQueues:
		return "3"
	case SectionCatalog:
		return "4"
	case SectionWorkOrders:
		return "5"
	default:
		return ""
	}
}

// ToggleFocus switches between left and right panes.
func ToggleFocus(f FocusArea) FocusArea {
	if f == FocusLeft {
		return FocusRight
	}
	return FocusLeft
}

// NextSection cycles left sections in display order.
func NextSection(s LeftSection) LeftSection {
	return LeftSection((int(s) + 1) % int(sectionCount))
}

// PrevSection cycles left sections backward.
func PrevSection(s LeftSection) LeftSection {
	n := int(s) - 1
	if n < 0 {
		n = int(sectionCount) - 1
	}
	return LeftSection(n)
}

// SectionFromKey maps digit keys 1-5 to sections.
func SectionFromKey(key string) (LeftSection, bool) {
	switch key {
	case "1":
		return SectionStatus, true
	case "2":
		return SectionApprovals, true
	case "3":
		return SectionQueues, true
	case "4":
		return SectionCatalog, true
	case "5":
		return SectionWorkOrders, true
	default:
		return SectionStatus, false
	}
}
