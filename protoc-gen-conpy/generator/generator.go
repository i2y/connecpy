package generator

import (
	"bytes"
	"errors"
	"fmt"
	"path"
	"strings"

	"github.com/golang/protobuf/protoc-gen-go/descriptor"
	plugin "github.com/golang/protobuf/protoc-gen-go/plugin"
	"google.golang.org/protobuf/proto"
)

func Generate(r *plugin.CodeGeneratorRequest) *plugin.CodeGeneratorResponse {
	resp := &plugin.CodeGeneratorResponse{}
	resp.SupportedFeatures = proto.Uint64(uint64(plugin.CodeGeneratorResponse_FEATURE_PROTO3_OPTIONAL))

	files := r.GetFileToGenerate()
	for _, fileName := range files {
		fd, err := getFileDescriptor(r.GetProtoFile(), fileName)
		if err != nil {
			resp.Error = proto.String("File[" + fileName + "][descriptor]: " + err.Error())
			return resp
		}

		conpyFile, err := GenerateConPyFile(fd)
		if err != nil {
			resp.Error = proto.String("File[" + fileName + "][generate]: " + err.Error())
			return resp
		}
		resp.File = append(resp.File, conpyFile)
	}
	return resp
}

func GenerateConPyFile(fd *descriptor.FileDescriptorProto) (*plugin.CodeGeneratorResponse_File, error) {
	name := fd.GetName()

	vars := ConPyTemplateVariables{
		FileName:              name,
		FileNameWithoutSuffix: strings.TrimSuffix(name, path.Ext(name)),
	}

	svcs := fd.GetService()
	for _, svc := range svcs {
		svcURL := fmt.Sprintf("%s.%s", fd.GetPackage(), svc.GetName())
		conpySvc := &ConPyService{
			Name:       svc.GetName(),
			ServiceURL: svcURL,
		}

		for _, method := range svc.GetMethod() {
			conpyMethod := &ConPyMethod{
				ServiceURL:  svcURL,
				ServiceName: conpySvc.Name,
				Name:        method.GetName(),
				InputType:   getSymbolName(method.GetInputType()),
				OutputType:  getSymbolName(method.GetOutputType()),
			}

			conpySvc.Methods = append(conpySvc.Methods, conpyMethod)
		}
		vars.Services = append(vars.Services, conpySvc)
	}

	var buf = &bytes.Buffer{}
	err := ConPyTemplate.Execute(buf, vars)
	if err != nil {
		return nil, err
	}

	resp := &plugin.CodeGeneratorResponse_File{
		Name:    proto.String(strings.TrimSuffix(name, path.Ext(name)) + "_conpy.py"),
		Content: proto.String(buf.String()),
	}

	return resp, nil
}

func getSymbolName(name string) string {
	parts := strings.Split(name, ".")
	return parts[len(parts)-1]
}

func getFileDescriptor(files []*descriptor.FileDescriptorProto, name string) (*descriptor.FileDescriptorProto, error) {
	//Assumption: Number of files will not be large enough to justify making a map
	for _, f := range files {
		if f.GetName() == name {
			return f, nil
		}
	}
	return nil, errors.New("could not find descriptor")
}
