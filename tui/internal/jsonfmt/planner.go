package jsonfmt

import (
	"fmt"
	"strings"
)

func isPlannerPlan(data map[string]interface{}) bool {
	if personas, ok := data["personas"]; ok && asStringList(personas) != nil {
		return true
	}
	if plan, ok := data["planner_plan"]; ok && asStringList(plan) != nil {
		return true
	}
	if _, ok := data["sub_goals"].(map[string]interface{}); ok {
		return true
	}
	if _, ok := data["planner_sub_goals"].(map[string]interface{}); ok {
		return true
	}
	return false
}

func normalizePlanner(data map[string]interface{}) map[string]interface{} {
	out := map[string]interface{}{}
	if v := asStringList(data["personas"]); len(v) > 0 {
		out["personas"] = v
	} else if v := asStringList(data["planner_plan"]); len(v) > 0 {
		out["personas"] = v
	}
	if v := asString(data["rationale"]); v != "" {
		out["rationale"] = v
	} else if v := asString(data["planner_rationale"]); v != "" {
		out["rationale"] = v
	}
	if m := asStringMap(data["sub_goals"]); len(m) > 0 {
		out["sub_goals"] = m
	} else if m := asStringMap(data["planner_sub_goals"]); len(m) > 0 {
		out["sub_goals"] = m
	}
	if m := asDependsOn(data["depends_on"]); len(m) > 0 {
		out["depends_on"] = m
	} else if m := asDependsOn(data["planner_depends_on"]); len(m) > 0 {
		out["depends_on"] = m
	}
	if v := asString(data["execution_mode"]); v != "" {
		out["execution_mode"] = v
	}
	if v := asString(data["synthesis_persona"]); v != "" {
		out["synthesis_persona"] = v
	}
	return out
}

func asDependsOn(value interface{}) map[string][]string {
	m, ok := value.(map[string]interface{})
	if !ok {
		return nil
	}
	out := make(map[string][]string)
	for k, v := range m {
		switch t := v.(type) {
		case []interface{}:
			for _, item := range t {
				out[k] = append(out[k], fmt.Sprint(item))
			}
		case string:
			if t != "" {
				out[k] = []string{t}
			}
		}
	}
	return out
}

// FormatPlanner renders planner JSON as readable text.
func FormatPlanner(data map[string]interface{}) string {
	norm := normalizePlanner(data)
	var lines []string
	lines = append(lines, "── Planner plan ──")

	if mode := asString(norm["execution_mode"]); mode != "" {
		lines = append(lines, "Mode: "+mode)
	}
	if synth := asString(norm["synthesis_persona"]); synth != "" {
		lines = append(lines, "Synthesis: "+synth)
	}
	if personas := asStringList(norm["personas"]); len(personas) > 0 {
		lines = append(lines, "Personas: "+strings.Join(personas, " → "))
	}
	if rationale := asString(norm["rationale"]); rationale != "" {
		lines = append(lines, "Rationale:\n"+indentBlock(rationale, "  "))
	}
	if subGoals := asStringMap(norm["sub_goals"]); len(subGoals) > 0 {
		lines = append(lines, "Sub-goals:")
		for persona, goal := range subGoals {
			lines = append(lines, fmt.Sprintf("  • %s: %s", persona, goal))
		}
	}
	if deps := asDependsOn(norm["depends_on"]); len(deps) > 0 {
		lines = append(lines, "Depends on:")
		for persona, parents := range deps {
			lines = append(lines, fmt.Sprintf("  • %s ← %s", persona, strings.Join(parents, ", ")))
		}
	}
	return strings.Join(lines, "\n")
}

func asString(value interface{}) string {
	if value == nil {
		return ""
	}
	if s, ok := value.(string); ok {
		return s
	}
	return strings.TrimSpace(fmt.Sprint(value))
}

func asStringList(value interface{}) []string {
	raw, ok := value.([]interface{})
	if !ok {
		if ss, ok := value.([]string); ok {
			return ss
		}
		return nil
	}
	out := make([]string, 0, len(raw))
	for _, item := range raw {
		if s, ok := item.(string); ok && s != "" {
			out = append(out, s)
		}
	}
	return out
}

func asStringMap(value interface{}) map[string]string {
	m, ok := value.(map[string]interface{})
	if !ok {
		return nil
	}
	out := make(map[string]string, len(m))
	for k, v := range m {
		if v == nil {
			continue
		}
		out[k] = asString(v)
	}
	return out
}
