package api

import (
	"bufio"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"time"
)

const (
	initialBackoff = time.Second
	maxBackoff     = 30 * time.Second
)

// StreamStatus represents SSE connection state.
type StreamStatus string

const (
	StreamIdle       StreamStatus = "idle"
	StreamConnecting StreamStatus = "connecting"
	StreamOpen       StreamStatus = "open"
	StreamClosed     StreamStatus = "closed"
	StreamError      StreamStatus = "error"
)

// EngagementStreamHandler receives parsed engagement SSE events.
type EngagementStreamHandler func(EngagementStreamEvent)

// StatusStreamHandler receives parsed global status SSE events.
type StatusStreamHandler func(StatusStreamEvent)

// RunEngagementStream connects to engagement SSE with reconnect backoff.
func RunEngagementStream(
	ctx context.Context,
	client *Client,
	engagementID string,
	onEvent EngagementStreamHandler,
	onStatus func(StreamStatus),
) {
	runSSE(ctx, client.EngagementStreamURL(engagementID), client, onStatus, func(data string) {
		var event EngagementStreamEvent
		if err := json.Unmarshal([]byte(data), &event); err != nil {
			return
		}
		onEvent(event)
	})
}

// RunStatusStream connects to global status SSE with reconnect backoff.
func RunStatusStream(
	ctx context.Context,
	client *Client,
	onEvent StatusStreamHandler,
	onStatus func(StreamStatus),
) {
	runSSE(ctx, client.StatusStreamURL(), client, onStatus, func(data string) {
		var event StatusStreamEvent
		if err := json.Unmarshal([]byte(data), &event); err != nil {
			return
		}
		if event.Kind == "heartbeat" {
			return
		}
		onEvent(event)
	})
}

func runSSE(
	ctx context.Context,
	streamURL string,
	client *Client,
	onStatus func(StreamStatus),
	onData func(string),
) {
	backoff := initialBackoff
	for {
		if ctx.Err() != nil {
			onStatus(StreamClosed)
			return
		}
		onStatus(StreamConnecting)

		connectCtx, cancel := context.WithTimeout(ctx, client.Timeout())
		resp, err := client.StreamRequest(connectCtx, streamURL)
		cancel()
		if err != nil || resp == nil || resp.StatusCode >= 400 {
			if resp != nil {
				resp.Body.Close()
			}
			onStatus(StreamError)
			if !sleepCtx(ctx, backoff) {
				return
			}
			backoff = min(backoff*2, maxBackoff)
			continue
		}

		backoff = initialBackoff
		onStatus(StreamOpen)
		readSSEBody(ctx, resp, onData)
		resp.Body.Close()

		if ctx.Err() != nil {
			onStatus(StreamClosed)
			return
		}
		onStatus(StreamError)
		if !sleepCtx(ctx, backoff) {
			return
		}
		backoff = min(backoff*2, maxBackoff)
	}
}

func readSSEBody(ctx context.Context, resp *http.Response, onData func(string)) {
	reader := bufio.NewReader(resp.Body)
	var buffer strings.Builder

	for {
		if ctx.Err() != nil {
			return
		}
		line, err := reader.ReadString('\n')
		if err != nil {
			if err == io.EOF {
				return
			}
			return
		}

		if line == "\n" || line == "\r\n" {
			if buffer.Len() > 0 {
				parseSSEChunk(buffer.String(), onData)
				buffer.Reset()
			}
			continue
		}

		buffer.WriteString(line)
	}
}

func parseSSEChunk(chunk string, onData func(string)) {
	for _, line := range strings.Split(chunk, "\n") {
		if strings.HasPrefix(line, "data:") {
			data := strings.TrimSpace(strings.TrimPrefix(line, "data:"))
			if data != "" {
				onData(data)
			}
		}
	}
}

func sleepCtx(ctx context.Context, d time.Duration) bool {
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return false
	case <-t.C:
		return true
	}
}

// MatchesInvestigation returns true when a status stream event relates to an investigation.
func MatchesInvestigation(event StatusStreamEvent, investigationID string) bool {
	if event.ID == investigationID {
		return true
	}
	payload := event.Payload
	if payload == nil {
		return false
	}
	candidates := []interface{}{
		payload["correlation_id"],
		payload["investigation_id"],
	}
	if ev, ok := payload["event"].(map[string]interface{}); ok {
		candidates = append(candidates, ev["correlation_id"])
	}
	for _, c := range candidates {
		if s, ok := c.(string); ok && s == investigationID {
			return true
		}
	}
	return false
}
