package jsonfmt

import (
	"encoding/json"
	"strings"
)

func isPlainObject(value interface{}) bool {
	m, ok := value.(map[string]interface{})
	return ok && m != nil
}

// ParseMaybe parses trimmed JSON object/array text.
func ParseMaybe(text string) (interface{}, bool) {
	trimmed := strings.TrimSpace(text)
	if trimmed == "" {
		return nil, false
	}
	if !strings.HasPrefix(trimmed, "{") && !strings.HasPrefix(trimmed, "[") {
		return nil, false
	}
	var out interface{}
	if err := json.Unmarshal([]byte(trimmed), &out); err != nil {
		return nil, false
	}
	return out, true
}

// parseFrom decodes the first JSON value in s (allows trailing text).
func parseFrom(s string) (interface{}, int, bool) {
	dec := json.NewDecoder(strings.NewReader(s))
	var out interface{}
	if err := dec.Decode(&out); err != nil {
		return nil, 0, false
	}
	return out, int(dec.InputOffset()), true
}

// findJSONStart returns index of embedded JSON in mixed prose+JSON text.
func findJSONStart(s string) int {
	for i := 0; i < len(s); i++ {
		if s[i] != '{' && s[i] != '[' {
			continue
		}
		if _, _, ok := parseFrom(s[i:]); ok {
			return i
		}
	}
	return -1
}

func formatLabel(key string) string {
	parts := strings.Split(key, "_")
	for i, p := range parts {
		if p == "" {
			continue
		}
		parts[i] = strings.ToUpper(p[:1]) + p[1:]
	}
	return strings.Join(parts, " ")
}
