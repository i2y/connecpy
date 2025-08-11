package generator

import (
	"bytes"
	"fmt"
	"path"
	"slices"
	"strings"

	plugin "github.com/golang/protobuf/protoc-gen-go/plugin"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/reflect/protodesc"
	"google.golang.org/protobuf/reflect/protoreflect"
	"google.golang.org/protobuf/types/descriptorpb"
)

func Generate(r *plugin.CodeGeneratorRequest) *plugin.CodeGeneratorResponse {
	resp := &plugin.CodeGeneratorResponse{}

	resp.SupportedFeatures = proto.Uint64(uint64(plugin.CodeGeneratorResponse_FEATURE_PROTO3_OPTIONAL) | uint64(plugin.CodeGeneratorResponse_FEATURE_SUPPORTS_EDITIONS))
	resp.MinimumEdition = proto.Int32(int32(descriptorpb.Edition_EDITION_PROTO3))
	resp.MaximumEdition = proto.Int32(int32(descriptorpb.Edition_EDITION_2023))

	files := r.GetFileToGenerate()
	if len(files) == 0 {
		resp.Error = proto.String("no files to generate")
		return resp
	}

	fds := &descriptorpb.FileDescriptorSet{
		File: r.GetProtoFile(),
	}
	reg, err := protodesc.NewFiles(fds)
	if err != nil {
		panic(err)
	}

	reg.RangeFiles(func(fd protoreflect.FileDescriptor) bool {
		if !slices.Contains(files, string(fd.Path())) {
			return true
		}

		// We don't generate any code for non-services
		if fd.Services().Len() == 0 {
			return true
		}

		connecpyFile, err := GenerateConnecpyFile(fd)
		if err != nil {
			resp.Error = proto.String("File[" + fd.Path() + "][generate]: " + err.Error())
			return false
		}
		resp.File = append(resp.File, connecpyFile)
		return true
	})

	return resp
}

func GenerateConnecpyFile(fd protoreflect.FileDescriptor) (*plugin.CodeGeneratorResponse_File, error) {
	filename := fd.Path()

	fileNameWithoutSuffix := strings.TrimSuffix(filename, path.Ext(filename))
	moduleName := strings.Join(strings.Split(fileNameWithoutSuffix, "/"), ".")

	vars := ConnecpyTemplateVariables{
		FileName:   filename,
		ModuleName: moduleName,
		Imports:    importStatements(fd),
	}

	svcs := fd.Services()
	packageName := string(fd.Package())
	for i := 0; i < svcs.Len(); i++ {
		svc := svcs.Get(i)
		connecpySvc := &ConnecpyService{
			Name:     string(svc.Name()),
			FullName: string(svc.FullName()),
			Package:  packageName,
		}

		methods := svc.Methods()
		for j := 0; j < methods.Len(); j++ {
			method := methods.Get(j)
			idempotencyLevel := "UNKNOWN"
			noSideEffects := false
			if mo, ok := method.Options().(*descriptorpb.MethodOptions); ok {
				switch mo.GetIdempotencyLevel() {
				case descriptorpb.MethodOptions_NO_SIDE_EFFECTS:
					idempotencyLevel = "NO_SIDE_EFFECTS"
					noSideEffects = true
				case descriptorpb.MethodOptions_IDEMPOTENT:
					idempotencyLevel = "IDEMPOTENT"
				}
			}
			endpointType := "unary"
			if method.IsStreamingClient() && method.IsStreamingServer() {
				endpointType = "bidi_stream"
			} else if method.IsStreamingClient() {
				endpointType = "client_stream"
			} else if method.IsStreamingServer() {
				endpointType = "server_stream"
			}
			connecpyMethod := &ConnecpyMethod{
				Package:          packageName,
				ServiceName:      connecpySvc.FullName,
				Name:             string(method.Name()),
				InputType:        symbolName(method.Input()),
				OutputType:       symbolName(method.Output()),
				EndpointType:     endpointType,
				Stream:           method.IsStreamingClient() || method.IsStreamingServer(),
				RequestStream:    method.IsStreamingClient(),
				ResponseStream:   method.IsStreamingServer(),
				NoSideEffects:    noSideEffects,
				IdempotencyLevel: idempotencyLevel,
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
		Name:    proto.String(strings.TrimSuffix(filename, path.Ext(filename)) + "_connecpy.py"),
		Content: proto.String(buf.String()),
	}

	return resp, nil
}

// https://github.com/grpc/grpc/blob/0dd1b2cad21d89984f9a1b3c6249d649381eeb65/src/compiler/python_generator_helpers.h#L67
func moduleName(filename string) string {
	fn, ok := strings.CutSuffix(filename, ".protodevel")
	if !ok {
		fn, _ = strings.CutSuffix(filename, ".proto")
	}
	fn = strings.ReplaceAll(fn, "-", "_")
	fn = strings.ReplaceAll(fn, "/", ".")
	return fn + "_pb2"
}

// https://github.com/grpc/grpc/blob/0dd1b2cad21d89984f9a1b3c6249d649381eeb65/src/compiler/python_generator_helpers.h#L80
func moduleAlias(filename string) string {
	mn := moduleName(filename)
	mn = strings.ReplaceAll(mn, "_", "__")
	mn = strings.ReplaceAll(mn, ".", "_dot_")
	return mn
}

func symbolName(msg protoreflect.MessageDescriptor) string {
	filename := string(msg.ParentFile().Path())
	name := string(msg.Name())
	return fmt.Sprintf("%s.%s", moduleAlias(filename), name)
}

func importStatements(file protoreflect.FileDescriptor) []ImportStatement {
	mods := map[string]string{}
	for i := 0; i < file.Services().Len(); i++ {
		svc := file.Services().Get(i)
		for j := 0; j < svc.Methods().Len(); j++ {
			method := svc.Methods().Get(j)
			inPkg := string(method.Input().ParentFile().Path())
			mods[moduleName(inPkg)] = moduleAlias(inPkg)
			outPkg := string(method.Output().ParentFile().Path())
			mods[moduleName(outPkg)] = moduleAlias(outPkg)
		}
	}

	imports := make([]ImportStatement, 0, len(mods))
	for mod, alias := range mods {
		imports = append(imports, ImportStatement{
			Name:  mod,
			Alias: alias,
		})
	}
	slices.SortFunc(imports, func(a, b ImportStatement) int {
		return strings.Compare(a.Name, b.Name)
	})
	return imports
}
