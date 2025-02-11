package generator

import (
	"bytes"
	"errors"
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
	if len(files) == 0 {
		resp.Error = proto.String("no files to generate")
		return resp
	}

	for _, fileName := range files {
		fd, err := getFileDescriptor(r.GetProtoFile(), fileName)
		if err != nil {
			resp.Error = proto.String("File[" + fileName + "][descriptor]: " + err.Error())
			return resp
		}

		connecpyFile, err := GenerateConnecpyFile(fd)
		if err != nil {
			resp.Error = proto.String("File[" + fileName + "][generate]: " + err.Error())
			return resp
		}
		resp.File = append(resp.File, connecpyFile)
	}
	return resp
}

func GenerateConnecpyFile(fd *descriptor.FileDescriptorProto) (*plugin.CodeGeneratorResponse_File, error) {
	name := fd.GetName()

	fileNameWithoutSuffix := strings.TrimSuffix(name, path.Ext(name))
	moduleName := strings.Join(strings.Split(fileNameWithoutSuffix, "/"), ".")

	vars := ConnecpyTemplateVariables{
		FileName:   name,
		ModuleName: moduleName,
	}

	svcs := fd.GetService()
	packageName := fd.GetPackage()
	for _, svc := range svcs {
		connecpySvc := &ConnecpyService{
			Name:    svc.GetName(),
			Package: packageName,
		}

		for _, method := range svc.GetMethod() {
			idempotencyLevel := method.Options.GetIdempotencyLevel()
			noSideEffects := idempotencyLevel == descriptor.MethodOptions_NO_SIDE_EFFECTS
			connecpyMethod := &ConnecpyMethod{
				Package:               packageName,
				ServiceName:           connecpySvc.Name,
				Name:                  method.GetName(),
				InputType:             getSymbolName(method.GetInputType(), packageName),
				InputTypeForProtocol:  getSymbolNameForProtocol(method.GetInputType(), packageName),
				OutputType:            getSymbolName(method.GetOutputType(), packageName),
				OutputTypeForProtocol: getSymbolNameForProtocol(method.GetOutputType(), packageName),
				NoSideEffects:         noSideEffects,
			}

			connecpySvc.Methods = append(connecpySvc.Methods, connecpyMethod)
		}
		vars.Services = append(vars.Services, connecpySvc)
	}

	var buf = &bytes.Buffer{}
	err := ConnecpyTemplate.Execute(buf, vars)
	if err != nil {
		return nil, err
	}

	resp := &plugin.CodeGeneratorResponse_File{
		Name:    proto.String(strings.TrimSuffix(name, path.Ext(name)) + "_connecpy.py"),
		Content: proto.String(buf.String()),
	}

	return resp, nil
}

func getLocalSymbolName(name string) string {
	parts := strings.Split(name, ".")
	return "_pb2." + parts[len(parts)-1]
}

func getSymbolName(name, localPackageName string) string {
	if strings.HasPrefix(name, "."+localPackageName) {
		return getLocalSymbolName(name)
	}

	return "_sym_db.GetSymbol(\"" + name[1:] + "\")"
}

func getSymbolNameForProtocol(name, localPackageName string) string {
	if strings.HasPrefix(name, "."+localPackageName) {
		return getLocalSymbolName(name)
	}

	return "Any"
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
