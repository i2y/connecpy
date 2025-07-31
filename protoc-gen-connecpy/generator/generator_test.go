package generator

import (
	"strings"
	"testing"

	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/reflect/protodesc"
	"google.golang.org/protobuf/types/descriptorpb"
	"google.golang.org/protobuf/types/pluginpb"
)

func TestGenerateConnecpyFile(t *testing.T) {
	tests := []struct {
		name     string
		input    *descriptorpb.FileDescriptorProto
		wantFile string
		wantErr  bool
	}{
		{
			name: "simple service",
			input: &descriptorpb.FileDescriptorProto{
				Name:    proto.String("test.proto"),
				Package: proto.String("test"),
				Service: []*descriptorpb.ServiceDescriptorProto{
					{
						Name: proto.String("TestService"),
						Method: []*descriptorpb.MethodDescriptorProto{
							{
								Name:       proto.String("TestMethod"),
								InputType:  proto.String(".test.TestRequest"),
								OutputType: proto.String(".test.TestResponse"),
							},
						},
					},
				},
				MessageType: []*descriptorpb.DescriptorProto{
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
			input: &descriptorpb.FileDescriptorProto{
				Name:    proto.String("multi.proto"),
				Package: proto.String("test"),
				Service: []*descriptorpb.ServiceDescriptorProto{
					{
						Name: proto.String("MultiService"),
						Method: []*descriptorpb.MethodDescriptorProto{
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
				MessageType: []*descriptorpb.DescriptorProto{
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
		req     *pluginpb.CodeGeneratorRequest
		wantErr bool
	}{
		{
			name: "empty request",
			req: &pluginpb.CodeGeneratorRequest{
				FileToGenerate: []string{},
			},
			wantErr: true,
		},
		{
			name: "valid request",
			req: &pluginpb.CodeGeneratorRequest{
				FileToGenerate: []string{"test.proto"},
				ProtoFile: []*descriptorpb.FileDescriptorProto{
					{
						Name:       proto.String("test.proto"),
						Package:    proto.String("test"),
						Dependency: []string{"other.proto"},
						Service: []*descriptorpb.ServiceDescriptorProto{
							{
								Name: proto.String("TestService"),
								Method: []*descriptorpb.MethodDescriptorProto{
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
						MessageType: []*descriptorpb.DescriptorProto{
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
						MessageType: []*descriptorpb.DescriptorProto{
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

func TestEdition2023Support(t *testing.T) {
	// Create a request with an Edition 2023 proto file
	edition2023 := descriptorpb.Edition_EDITION_2023
	
	req := &pluginpb.CodeGeneratorRequest{
		FileToGenerate: []string{"test_edition2023.proto"},
		ProtoFile: []*descriptorpb.FileDescriptorProto{
			{
				Name:    proto.String("test_edition2023.proto"),
				Package: proto.String("test.edition2023"),
				Edition: edition2023.Enum(),
				// Edition 2023 default: field_presence = EXPLICIT
				Options: &descriptorpb.FileOptions{
					Features: &descriptorpb.FeatureSet{
						FieldPresence: descriptorpb.FeatureSet_EXPLICIT.Enum(),
					},
				},
				Service: []*descriptorpb.ServiceDescriptorProto{
					{
						Name: proto.String("Edition2023Service"),
						Method: []*descriptorpb.MethodDescriptorProto{
							{
								Name:       proto.String("TestMethod"),
								InputType:  proto.String(".test.edition2023.TestRequest"),
								OutputType: proto.String(".test.edition2023.TestResponse"),
							},
						},
					},
				},
				MessageType: []*descriptorpb.DescriptorProto{
					{
						Name: proto.String("TestRequest"),
						Field: []*descriptorpb.FieldDescriptorProto{
							{
								Name:   proto.String("message"),
								Number: proto.Int32(1),
								Label:  descriptorpb.FieldDescriptorProto_LABEL_OPTIONAL.Enum(),
								Type:   descriptorpb.FieldDescriptorProto_TYPE_STRING.Enum(),
								// In Edition 2023, field presence is controlled by features
							},
						},
					},
					{
						Name: proto.String("TestResponse"),
						Field: []*descriptorpb.FieldDescriptorProto{
							{
								Name:   proto.String("result"),
								Number: proto.Int32(1),
								Label:  descriptorpb.FieldDescriptorProto_LABEL_OPTIONAL.Enum(),
								Type:   descriptorpb.FieldDescriptorProto_TYPE_STRING.Enum(),
							},
						},
					},
				},
			},
		},
	}

	// Call Generate
	resp := Generate(req)

	// Verify no error occurred
	if resp.GetError() != "" {
		t.Fatalf("Generate() failed for Edition 2023 proto: %v", resp.GetError())
	}

	// Verify the generator declared Edition support
	if resp.GetSupportedFeatures()&uint64(pluginpb.CodeGeneratorResponse_FEATURE_SUPPORTS_EDITIONS) == 0 {
		t.Error("Generator should declare FEATURE_SUPPORTS_EDITIONS")
	}

	// Verify minimum and maximum editions are set
	if resp.GetMinimumEdition() != int32(descriptorpb.Edition_EDITION_PROTO3) {
		t.Errorf("Expected minimum edition PROTO3, got %v", resp.GetMinimumEdition())
	}
	if resp.GetMaximumEdition() != int32(descriptorpb.Edition_EDITION_2023) {
		t.Errorf("Expected maximum edition 2023, got %v", resp.GetMaximumEdition())
	}

	// Verify a file was generated
	if len(resp.GetFile()) == 0 {
		t.Error("No files generated for Edition 2023 proto")
	} else {
		generatedFile := resp.GetFile()[0]
		if generatedFile.GetName() != "test_edition2023_connecpy.py" {
			t.Errorf("Expected filename test_edition2023_connecpy.py, got %v", generatedFile.GetName())
		}
		
		// Verify the generated content includes the service
		content := generatedFile.GetContent()
		if !strings.Contains(content, "class Edition2023Service") {
			t.Error("Generated code missing Edition2023Service class")
		}
	}
}
