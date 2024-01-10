# protoc-gen-connecpy
protobuf plugin for generating Connecpy server and client code.

## Installing and using plugin
1. Make sure your [GO](https://golang.org/) environment, [Protoc](https://github.com/protocolbuffers/protobuf/releases/latest) compiler is properly setup.
2. Install the plugin : `go install`
This will build the plugin and will be available at `$GOBIN` directory which is usually `$GOPATH/bin`
3. Generate code for `haberdasher.proto` using connecpy plugin :
`protoc --python_out=./ --connecpy_out=./ haberdasher.proto`
  - python_out : The directory where generated Protobuf Python code needs to be saved.
  - connecpy_out : The directory where generated Connecpy Python server and client code needs to be saved.

The compiler gives the error below if it's not able to find the plugin.

```
--connecpy_out: protoc-gen-connecpy: Plugin failed with status code 1.
```

In such cases, you can give absolute path to plugin, eg: `--plugin=protoc-gen-connecpy=$GOBIN/protoc-gen-connecpy`
