package generator

import (
	"strings"
)

type Naming uint32

const (
	// NamingPEP is the naming convention that follows PEP8, notably using
	// snake_case method names.
	NamingPEP Naming = iota
	// NamingGoogle is the naming convention that follows Google internal style,
	// notably using PascalCase method names.
	NamingGoogle
)

// Config is the configuration for code generation.
type Config struct {
	// Naming is the naming convention to use for generated symbols.
	Naming Naming
}

func parseConfig(p string) Config {
	// Proto parameters should always be treated as CSV to match Buf's pattern.
	// There is no consistency on the items themselves but we use key=value.
	parts := strings.Split(p, ",")
	cfg := Config{}
	for _, part := range parts {
		part = strings.TrimSpace(part)
		key, value, ok := strings.Cut(part, "=")
		if !ok {
			continue
		}
		key = strings.TrimSpace(key)
		value = strings.TrimSpace(value)
		switch key {
		case "naming":
			switch value {
			case "pep":
				cfg.Naming = NamingPEP
			case "google":
				cfg.Naming = NamingGoogle
			}
		}
	}
	return cfg
}
