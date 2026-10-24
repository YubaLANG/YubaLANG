# Calling C functions from YubaLANG

YubaLANG's initial C ABI bridge can call functions in a local native library:

```text
ffi call <library-path> <symbol> <return-type> [<argument-type> <value> ...] [-> <destination>]
```

Paths may be quoted and are resolved relative to the YubaLANG source file (or
the current working directory when executing an in-memory program). Libraries
are loaded once per interpreter runtime and kept loaded for that runtime's
lifetime.

## Supported ABI

Arguments support `i32`, `i64`, `f64`, and `bool`. Return types support those
four types plus `void`. Integer arguments are range-checked signed values;
`f64` takes a finite number; and `bool` takes a YubaLANG boolean. Non-void
functions require `-> <destination>` with an existing `int`, `float`, or `bool`
variable matching the declared return type. Void functions do not take a
destination.

The bridge uses the platform C calling convention (`cdecl`); on 64-bit Windows
this is the standard Windows x64 convention. Function signatures must match
the declaration exactly. YubaLANG reports library loading errors, missing
symbols, unsupported types, invalid arguments, and incompatible destinations
as source diagnostics.

The bridge relies on Python's `ctypes.CDLL` and the host platform's native
dynamic-library loader. The library must be built for the same operating
system, architecture, and calling convention as the running interpreter;
YubaLANG does not cross-compile or translate ABIs.

## Ownership and safety

Only values passed by value are supported. No pointers, strings, arrays,
structures, callbacks, variadic functions, or ownership transfer cross the
boundary. Thus the bridge itself does not create C-side values whose lifetime
must be managed. A C function may still have its own side effects and can
crash or corrupt the process; only load and call errors that Python can detect
are reported. Call only libraries you trust.

## Example

[`examples/ffi_add.c`](../examples/ffi_add.c) exports a function that adds two
32-bit integers. Compile it as a shared library using a C compiler:

```sh
cc -shared -fPIC examples/ffi_add.c -o examples/libnative_add.so
```

On macOS, use `-dynamiclib` instead of `-shared` and name the output
`examples/libnative_add.dylib`. On Windows with the Visual C compiler, run:

```powershell
cl /nologo /LD examples\ffi_add.c /link /OUT:examples\libnative_add.dll
```

Set the library filename in [`examples/ffi_add.yl`](../examples/ffi_add.yl) to
the matching platform library, then run the program from the repository root.
It should print `42`. A C compiler is needed to build the library; the
YubaLANG runtime itself does not compile C code.

The portable test suite mocks the native loader and, when a C compiler is
available, also builds and calls the example library.
