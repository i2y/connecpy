# Connecpy Rationale

Much of the design of Connecpy is based on the principle of providing the best
experience we can think of for the 99% use case, while also supporting the
rest, possibly through more somewhat more complicated means. This number refers
to usages of Connecpy, not users, as even more advanced use cases will
generally be a subset of usage for even a single user. So we think this
philosophy is a win for everybody.

Below are documentation of notable design decisions in this library that may

## Go instead of Python for protoc plugin

Because Connecpy will be used in Python projects, it seems natural to implement
the code generation plugin in Python as well. However, many codebases include
multiple languages that communicate with each other with RPC - this means that
the same protos are generally compiled to multiple languages. In such cases,
it is often easier to compile the protos together for all languages, needing
a language-agnostic way of compilation. Using Go allows us to provide static
binaries that will run anywhere and can be easily installed for this use case.
They can also be invoked with `go run` as needed - notably, as Buf, the best
solution for compiling protos, is also written in Go, we believe the plugin
will also have no worse of an experience being written in Go and managed in
the same way.

We can still support easy onboarding for Python-only use cases by publishing
wheels with the plugin binaries, similar to how tools like Ruff are published.
This should mean that all users can easily onboard the plugin.
