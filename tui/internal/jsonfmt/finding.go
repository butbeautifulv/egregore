package jsonfmt

import (
	"fmt"
	"strings"
)

var findingMarkers = map[string]bool{
	"summary": true, "finding": true, "topic": true, "evidence": true,
	"risk_level": true, "severity": true, "priority": true, "analysis": true,
	"message": true, "data_gaps": true, "recommendations": true,
	"recommended_actions": true, "recommended_remediation": true,
	"mitre_tactics": true, "mitre_techniques": true, "telemetry_level": true,
	"confidence": true, "affected_assets": true, "affected_systems": true,
	"timeline": true, "references": true, "finding_type": true,
	"attack_phase": true, "hypothesis": true, "remediation": true,
	"framework": true, "control_id": true, "compliance_status": true,
	"gaps": true, "reproduction_steps": true, "incident_id": true,
	"iocs": true, "ttps": true, "artifacts": true,
}

var metaKeys = map[string]bool{
	"persona": true, "job_id": true, "agent": true, "event_id": true,
	"correlation_id": true, "tenant_id": true, "sandbox_id": true,
}

func isFindingPayload(data map[string]interface{}) bool {
	if isPlannerPlan(data) {
		return false
	}
	for key := range data {
		if findingMarkers[key] {
			return true
		}
	}
	return false
}

func findingBody(item map[string]interface{}) map[string]interface{} {
	if nested, ok := item["finding"].(map[string]interface{}); ok {
		return nested
	}
	return item
}

func hasValue(value interface{}) bool {
	if value == nil {
		return false
	}
	switch t := value.(type) {
	case string:
		return strings.TrimSpace(t) != ""
	case []interface{}:
		return len(t) > 0
	case map[string]interface{}:
		return len(t) > 0
	default:
		return true
	}
}

func isDisplayableKey(key string) bool {
	return !metaKeys[key] && key != "raw_response" && key != "evidence_manifest"
}

// FormatFinding renders a structured finding for the terminal.
func FormatFinding(data map[string]interface{}) string {
	body := findingBody(data)
	if len(body) == 0 {
		return "—"
	}

	if raw, ok := body["raw_response"].(string); ok && strings.TrimSpace(raw) != "" {
		if parsed, ok := ParseMaybe(raw); ok {
			if m, ok := parsed.(map[string]interface{}); ok && isFindingPayload(m) {
				return FormatFinding(m)
			}
			return Indent(parsed)
		}
		return strings.TrimSpace(raw)
	}

	priority := []string{
		"summary", "risk_level", "severity", "priority", "analysis", "message",
		"hypothesis", "evidence", "data_gaps", "recommendations", "recommended_actions",
		"recommended_remediation", "mitre_tactics", "mitre_techniques", "timeline",
		"remediation", "confidence", "finding_type",
	}
	rendered := make(map[string]bool)
	var lines []string

	for _, key := range priority {
		if !hasValue(body[key]) {
			continue
		}
		lines = append(lines, formatField(key, body[key]))
		rendered[key] = true
	}

	for key, value := range body {
		if rendered[key] || !isDisplayableKey(key) || !hasValue(value) {
			continue
		}
		lines = append(lines, formatField(key, value))
	}

	if len(lines) == 0 {
		return Indent(body)
	}
	return strings.Join(lines, "\n")
}

func formatField(key string, value interface{}) string {
	label := formatLabel(key)
	switch t := value.(type) {
	case string:
		return label + ":\n  " + indentBlock(t, "  ")
	case []interface{}:
		if len(t) == 0 {
			return label + ": —"
		}
		if allPrimitives(t) {
			var items []string
			for _, item := range t {
				items = append(items, "  • "+primitiveString(item))
			}
			return label + ":\n" + strings.Join(items, "\n")
		}
		return label + ":\n" + indentBlock(Indent(t), "  ")
	case map[string]interface{}:
		return label + ":\n" + indentBlock(Indent(t), "  ")
	default:
		return label + ": " + primitiveString(value)
	}
}

func allPrimitives(items []interface{}) bool {
	for _, item := range items {
		switch item.(type) {
		case string, float64, bool, nil:
		default:
			return false
		}
	}
	return true
}

func primitiveString(value interface{}) string {
	if value == nil {
		return "null"
	}
	switch t := value.(type) {
	case string:
		return t
	case float64:
		if t == float64(int64(t)) {
			return fmt.Sprintf("%d", int64(t))
		}
		return fmt.Sprintf("%v", t)
	case bool:
		return fmt.Sprintf("%t", t)
	default:
		return fmt.Sprint(t)
	}
}

func indentBlock(text, prefix string) string {
	lines := strings.Split(text, "\n")
	for i, line := range lines {
		if line != "" {
			lines[i] = prefix + line
		}
	}
	return strings.Join(lines, "\n")
}

// FormatOutcome renders OperatorOutcome-style final_report for TUI.
func FormatOutcome(data map[string]interface{}) string {
	if data == nil {
		return "—"
	}
	title := str(data["title"])
	if title == "" {
		title = str(data["topic"])
	}
	if title == "" {
		title = "Work order outcome"
	}
	summary := str(data["summary"])
	lines := []string{title}
	if kind := str(data["kind"]); kind != "" {
		lines = append(lines, "Kind: "+kind)
	}
	if summary != "" {
		lines = append(lines, "", summary)
	}
	if recs, ok := data["recommendations"].([]interface{}); ok && len(recs) > 0 {
		lines = append(lines, "", "Recommendations:")
		for _, item := range recs {
			text := strings.TrimSpace(fmt.Sprint(item))
			if text != "" {
				lines = append(lines, "- "+text)
			}
		}
	}
	return strings.Join(lines, "\n")
}

func str(v interface{}) string {
	if v == nil {
		return ""
	}
	if s, ok := v.(string); ok {
		return s
	}
	return fmt.Sprint(v)
}
