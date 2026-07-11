package config

import (
	"os"
	"strconv"
	"strings"
	"time"
)

// Config holds TUI connection settings.
type Config struct {
	APIURL        string
	APIToken      string
	TenantID      string
	SSEEnabled    bool
	ConsoleLayout bool
	LegacyLayout  bool
	Timeout       time.Duration
}

// Load reads configuration from environment variables.
func Load() Config {
	timeout := 20 * time.Second
	if raw := os.Getenv("EGREGORE_API_TIMEOUT_MS"); raw != "" {
		if ms, err := strconv.Atoi(raw); err == nil && ms > 0 {
			timeout = time.Duration(ms) * time.Millisecond
		}
	}

	apiURL := strings.TrimRight(envOr("EGREGORE_API_URL", "http://127.0.0.1:8080"), "/")
	token := envOr("EGREGORE_API_TOKEN", "egregore-demo-token")

	sse := true
	if raw := os.Getenv("EGREGORE_SSE"); raw != "" {
		sse = raw == "1" || strings.EqualFold(raw, "true")
	}

	consoleLayout := true
	if raw := os.Getenv("EGREGORE_TUI_CONSOLE"); raw != "" {
		consoleLayout = raw == "1" || strings.EqualFold(raw, "true")
	}
	legacy := os.Getenv("EGREGORE_TUI_LEGACY") == "1" || strings.EqualFold(os.Getenv("EGREGORE_TUI_LEGACY"), "true")
	if legacy {
		consoleLayout = false
	}

	return Config{
		APIURL:        apiURL,
		APIToken:      token,
		TenantID:      envOr("EGREGORE_TENANT_ID", "default"),
		SSEEnabled:    sse,
		ConsoleLayout: consoleLayout,
		LegacyLayout:  legacy,
		Timeout:       timeout,
	}
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
