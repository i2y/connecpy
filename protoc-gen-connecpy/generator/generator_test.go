package generator

import (
	"strings"
	"testing"

	"github.com/golang/protobuf/protoc-gen-go/descriptor"
	plugin "github.com/golang/protobuf/protoc-gen-go/plugin"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/reflect/protodesc"
)

func TestGenerateConnecpyFile(t *testing.T) {
	tests := []struct {
		name     string
		input    *descriptor.FileDescriptorProto
		wantFile string
		wantErr  bool
	}{
		{
			name: "simple service",
			input: &descriptor.FileDescriptorProto{
				Name:    proto.String("test.proto"),
				Package: proto.String("test"),
				Service: []*descriptor.ServiceDescriptorProto{
					{
						Name: proto.String("TestService"),
						Method: []*descriptor.MethodDescriptorProto{
							{
								Name:       proto.String("TestMethod"),
								InputType:  proto.String(".test.TestRequest"),
								OutputType: proto.String(".test.TestResponse"),
							},
						},
					},
				},
				MessageType: []*descriptor.DescriptorProto{
					{
						Name: proto.String("TestRequest"),
					},
					{
						Name: proto.String("TestResponse"),
					},
				},
			},
			wantFile: "test_connecpy.py",
			wantErr:  false,
		},
		{
			name: "service with multiple methods",
			input: &descriptor.FileDescriptorProto{
				Name:    proto.String("multi.proto"),
				Package: proto.String("test"),
				Service: []*descriptor.ServiceDescriptorProto{
					{
						Name: proto.String("MultiService"),
						Method: []*descriptor.MethodDescriptorProto{
							{
								Name:       proto.String("Method1"),
								InputType:  proto.String(".test.Request1"),
								OutputType: proto.String(".test.Response1"),
							},
							{
								Name:       proto.String("Method2"),
								InputType:  proto.String(".test.Request2"),
								OutputType: proto.String(".test.Response2"),
							},
						},
					},
				},
				MessageType: []*descriptor.DescriptorProto{
					{
						Name: proto.String("Request1"),
					},
					{
						Name: proto.String("Response1"),
					},
					{
						Name: proto.String("Request2"),
					},
					{
						Name: proto.String("Response2"),
					},
				},
			},
			wantFile: "multi_connecpy.py",
			wantErr:  false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			fd, err := protodesc.NewFile(tt.input, nil)
			if err != nil {
				t.Fatalf("Failed to create FileDescriptorProto: %v", err)
				return
			}
			got, err := GenerateConnecpyFile(fd)
			if (err != nil) != tt.wantErr {
				t.Errorf("GenerateConnecpyFile() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if err == nil {
				if got.GetName() != tt.wantFile {
					t.Errorf("GenerateConnecpyFile() got filename = %v, want %v", got.GetName(), tt.wantFile)
				}

				content := got.GetContent()
				if !strings.Contains(content, "from typing import Iterable, Mapping, Protocol") {
					t.Error("Generated code missing required imports")
				}
				if !strings.Contains(content, "class "+strings.Split(tt.input.GetService()[0].GetName(), ".")[0]) {
					t.Error("Generated code missing service class")
				}
			}
		})
	}
}

func TestGenerate(t *testing.T) {
	tests := []struct {
		name    string
		req     *plugin.CodeGeneratorRequest
		wantErr bool
	}{
		{
			name: "empty request",
			req: &plugin.CodeGeneratorRequest{
				FileToGenerate: []string{},
			},
			wantErr: true,
		},
		{
			name: "valid request",
			req: &plugin.CodeGeneratorRequest{
				FileToGenerate: []string{"test.proto"},
				ProtoFile: []*descriptor.FileDescriptorProto{
					{
						Name:       proto.String("test.proto"),
						Package:    proto.String("test"),
						Dependency: []string{"other.proto"},
						Service: []*descriptor.ServiceDescriptorProto{
							{
								Name: proto.String("TestService"),
								Method: []*descriptor.MethodDescriptorProto{
									{
										Name:       proto.String("TestMethod"),
										InputType:  proto.String(".test.TestRequest"),
										OutputType: proto.String(".test.TestResponse"),
									},
									{
										Name:       proto.String("TestMethod2"),
										InputType:  proto.String(".otherpackage.OtherRequest"),
										OutputType: proto.String(".otherpackage.OtherResponse"),
									},
								},
							},
						},
						MessageType: []*descriptor.DescriptorProto{
							{
								Name: proto.String("TestRequest"),
							},
							{
								Name: proto.String("TestResponse"),
							},
						},
					},
					{
						Name:    proto.String("other.proto"),
						Package: proto.String("otherpackage"),
						MessageType: []*descriptor.DescriptorProto{
							{
								Name: proto.String("OtherRequest"),
							},
							{
								Name: proto.String("OtherResponse"),
							},
						},
					},
				},
			},
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			resp := Generate(tt.req)
			if tt.wantErr {
				if resp.GetError() == "" {
					t.Error("Generate() expected error but got none")
				}
			} else {
				if resp.GetError() != "" {
					t.Errorf("Generate() unexpected error: %v", resp.GetError())
				}
				if len(resp.GetFile()) == 0 {
					t.Error("Generate() returned no files")
				}
			}
		})
	}
}
