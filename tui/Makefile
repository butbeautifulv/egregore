.PHONY: run build test tidy

run:
	go run ./cmd/egregore-tui

build:
	@mkdir -p bin
	go build -o bin/egregore-tui ./cmd/egregore-tui

test:
	go test ./...

tidy:
	go mod tidy
