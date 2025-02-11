package generator

import (
	"bytes"
	"strings"
	"testing"

	"github.com/golang/protobuf/protoc-gen-go/descriptor"
)

func TestConnecpyTemplate(t *testing.T) {
	tests := []struct {
		name     string
		vars     ConnecpyTemplateVariables
		contains []string
	}{
		{
			name: "simple service",
			vars: ConnecpyTemplateVariables{
				FileName:   "test.proto",
				ModuleName: "test",
				Services: []*ConnecpyService{
					{
						Package: "test",
						Name:    "TestService",
						Methods: []*ConnecpyMethod{
							{
								Package:               "test",
								ServiceName:           "TestService",
								Name:                  "TestMethod",
								InputType:             "_pb2.TestRequest",
								InputTypeForProtocol:  "_pb2.TestRequest",
								OutputType:            "_pb2.TestResponse",
								OutputTypeForProtocol: "_pb2.TestResponse",
								NoSideEffects:         false,
							},
						},
					},
				},
			},
			contains: []string{
				"from typing import Any, Protocol, Union",
				"class TestService(Protocol):",
				"class TestServiceServer(ConnecpyServer):",
				"def TestMethod",
				`allowed_methods=("POST",)`,
			},
		},
		{
			name: "service with no side effects method",
			vars: ConnecpyTemplateVariables{
				FileName:   "test.proto",
				ModuleName: "test",
				Services: []*ConnecpyService{
					{
						Package: "test",
						Name:    "TestService",
						Methods: []*ConnecpyMethod{
							{
								Package:               "test",
								ServiceName:           "TestService",
								Name:                  "GetData",
								InputType:             "_pb2.GetRequest",
								InputTypeForProtocol:  "_pb2.GetRequest",
								OutputType:            "_pb2.GetResponse",
								OutputTypeForProtocol: "_pb2.GetResponse",
								NoSideEffects:         true,
							},
						},
					},
				},
			},
			contains: []string{
				`allowed_methods=("GET", "POST")`,
				"use_get: bool = False",
				`method = "GET" if use_get else "POST"`,
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var buf bytes.Buffer
			err := ConnecpyTemplate.Execute(&buf, tt.vars)
			if err != nil {
				t.Fatalf("Template execution failed: %v", err)
			}

			result := buf.String()
			for _, want := range tt.contains {
				if !strings.Contains(result, want) {
					t.Errorf("Generated code missing expected content: %q, got: %q", want, result)
				}
			}
		})
	}
}

func TestConnecpyTemplateWithMethodOptions(t *testing.T) {
	noSideEffects := descriptor.MethodOptions_NO_SIDE_EFFECTS

	tests := []struct {
		name               string
		methodOptions      *descriptor.MethodOptions
		wantAllowedMethods string
	}{
		{
			name:               "regular method",
			methodOptions:      nil,
			wantAllowedMethods: `allowed_methods=("POST",)`,
		},
		{
			name: "no side effects method",
			methodOptions: &descriptor.MethodOptions{
				IdempotencyLevel: &noSideEffects,
			},
			wantAllowedMethods: `allowed_methods=("GET", "POST")`,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			vars := ConnecpyTemplateVariables{
				FileName:   "test.proto",
				ModuleName: "test",
				Services: []*ConnecpyService{
					{
						Package: "test",
						Name:    "TestService",
						Methods: []*ConnecpyMethod{
							{
								Package:       "test",
								ServiceName:   "TestService",
								Name:          "TestMethod",
								NoSideEffects: tt.methodOptions != nil && tt.methodOptions.GetIdempotencyLevel() == descriptor.MethodOptions_NO_SIDE_EFFECTS,
							},
						},
					},
				},
			}

			var buf bytes.Buffer
			err := ConnecpyTemplate.Execute(&buf, vars)
			if err != nil {
				t.Fatalf("Template execution failed: %v", err)
			}

			result := buf.String()
			if !strings.Contains(result, tt.wantAllowedMethods) {
				t.Errorf("Generated code missing expected allowed_methods: %q", tt.wantAllowedMethods)
			}
		})
	}
}
