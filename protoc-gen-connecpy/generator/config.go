package generator

import (
	"strings"
)

// Naming is the naming convention to use for generated symbols.
type Naming uint32

const (
	// NamingPEP is the naming convention that follows PEP8, notably using
	// snake_case method names.
	NamingPEP Naming = iota
	// NamingGoogle is the naming convention that follows Google internal style,
	// notably using PascalCase method names.
	NamingGoogle
)

// Imports is how to import dependencies in the generated code.
type Imports uint32

const (
	// ImportsAbsolute uses absolute imports following the proto's package definition.
	ImportsAbsolute Imports = iota

	// ImportsRelative uses relative imports.
	ImportsRelative
)

// Config is the configuration for code generation.
type Config struct {
	// Naming is the naming convention to use for generated symbols.
	Naming Naming

	// Imports is how to import dependencies in the generated code.
	Imports Imports

	// TransportAPI enables generation of experimental Transport API support.
	// This includes Protocol types, gRPC wrappers, and factory functions.
	TransportAPI bool
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
		case "imports":
			switch value {
			case "absolute":
				cfg.Imports = ImportsAbsolute
			case "relative":
				cfg.Imports = ImportsRelative
			}
		case "transport_api":
			switch value {
			case "true", "1", "yes":
				cfg.TransportAPI = true
			case "false", "0", "no":
				cfg.TransportAPI = false
			}
		}
	}
	return cfg
}
