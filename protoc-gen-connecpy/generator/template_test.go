package generator

import (
	"bytes"
	"strings"
	"testing"
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
								Package:       "test",
								ServiceName:   "TestService",
								Name:          "TestMethod",
								PythonName:    "TestMethod",
								InputType:     "_pb2.TestRequest",
								OutputType:    "_pb2.TestResponse",
								NoSideEffects: false,
							},
						},
					},
				},
			},
			contains: []string{
				"from collections.abc import Iterable, Mapping",
				"class TestService(Protocol):",
				"class TestServiceASGIApplication(ConnecpyASGIApplication):",
				"def TestMethod",
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
								Package:       "test",
								ServiceName:   "TestService",
								Name:          "GetData",
								PythonName:    "GetData",
								InputType:     "_pb2.GetRequest",
								OutputType:    "_pb2.GetResponse",
								NoSideEffects: true,
							},
						},
					},
				},
			},
			contains: []string{
				"use_get: bool = False",
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
