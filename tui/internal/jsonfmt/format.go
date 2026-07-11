package jsonfmt

import (
	"encoding/json"
	"fmt"
	"strings"

	"github.com/butbeautifulv/egregore/tui/internal/textutil"
)

// Indent pretty-prints any JSON value.
func Indent(value interface{}) string {
	if value == nil {
		return "null"
	}
	b, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return fmt.Sprint(value)
	}
	return string(b)
}

func formatParsed(value interface{}) string {
	if m, ok := value.(map[string]interface{}); ok {
		if isPlannerPlan(m) {
			return FormatPlanner(m)
		}
		if isFindingPayload(m) {
			return FormatFinding(m)
		}
		return Indent(m)
	}
	if arr, ok := value.([]interface{}); ok {
		if len(arr) == 1 {
			if m, ok := arr[0].(map[string]interface{}); ok {
				return formatParsed(m)
			}
		}
		return Indent(arr)
	}
	return Indent(value)
}

// FormatMessage formats agent text: prose, pure JSON, or mixed prose+JSON.
func FormatMessage(text string, width int) string {
	text = strings.TrimSpace(text)
	if text == "" {
		return ""
	}
	if width < 20 {
		width = 80
	}

	if parsed, ok := ParseMaybe(text); ok {
		return textutil.WrapBlock(formatParsed(parsed), width)
	}

	if idx := findJSONStart(text); idx >= 0 {
		var parts []string
		if idx > 0 {
			prose := strings.TrimSpace(text[:idx])
			if prose != "" {
				parts = append(parts, textutil.WrapBlock(prose, width))
			}
		}
		remaining := strings.TrimSpace(text[idx:])
		for remaining != "" {
			parsed, n, ok := parseFrom(remaining)
			if !ok {
				parts = append(parts, textutil.WrapBlock(remaining, width))
				break
			}
			parts = append(parts, textutil.WrapBlock(formatParsed(parsed), width))
			remaining = strings.TrimSpace(remaining[n:])
			if remaining != "" && remaining[0] != '{' && remaining[0] != '[' {
				if next := findJSONStart(remaining); next > 0 {
					parts = append(parts, textutil.WrapBlock(strings.TrimSpace(remaining[:next]), width))
					remaining = strings.TrimSpace(remaining[next:])
					continue
				}
				parts = append(parts, textutil.WrapBlock(remaining, width))
				break
			}
		}
		return strings.Join(parts, "\n\n")
	}

	return textutil.WrapBlock(text, width)
}

// FormatValue formats a JSON value with domain-specific renderers when applicable.
func FormatValue(value interface{}) string {
	return formatParsed(value)
}

// FormatFindingsSummary renders investigation findings for the findings pane.
func FormatFindingsSummary(items []map[string]interface{}) string {
	if len(items) == 0 {
		return "No structured findings yet."
	}
	var blocks []string
	for i, item := range items {
		header := fmt.Sprintf("── Finding %d", i+1)
		if persona := asString(item["persona"]); persona != "" {
			header += " · " + persona
		}
		if jobID := asString(item["job_id"]); jobID != "" {
			header += " (" + jobID + ")"
		}
		header += " ──"

		body := item
		if finding, ok := item["finding"].(map[string]interface{}); ok {
			body = finding
		}
		block := header + "\n" + FormatFinding(body)
		blocks = append(blocks, block)
	}
	return strings.Join(blocks, "\n\n")
}

// FormatPlannerFromDetail builds planner text from investigation detail fields.
func FormatPlannerFromDetail(plan []string, rationale string, subGoals map[string]string, dependsOn map[string][]string, executionMode, synthesisPersona *string) string {
	data := map[string]interface{}{
		"planner_plan":      plan,
		"planner_rationale": rationale,
		"planner_sub_goals": subGoals,
		"planner_depends_on": dependsOn,
	}
	if executionMode != nil {
		data["execution_mode"] = *executionMode
	}
	if synthesisPersona != nil {
		data["synthesis_persona"] = *synthesisPersona
	}
	return FormatPlanner(data)
}
