# protoc-gen-conpy
protobuf plugin for generating ConPy server and client code.

## Installing and using plugin
1. Make sure your [GO](https://golang.org/) environment, [Protoc](https://github.com/protocolbuffers/protobuf/releases/latest) compiler is properly setup.
2. Install the plugin : `go install`
This will build the plugin and will be available at `$GOBIN` directory which is usually `$GOPATH/bin`
3. Generate code for `haberdasher.proto` using conpy plugin :
`protoc --python_out=./ --conpy_out=./ haberdasher.proto`
  - python_out : The directory where generated Protobuf Python code needs to be saved.
  - conpy_out : The directory where generated ConPy Python server and client code needs to be saved.

The compiler gives the error below if it's not able to find the plugin.

```
--conpy_out: protoc-gen-conpy: Plugin failed with status code 1.
```

In such cases, you can give absolute path to plugin, eg: `--plugin=protoc-gen-conpy=$GOBIN/protoc-gen-conpy`
