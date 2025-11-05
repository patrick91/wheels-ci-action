# Wheels CI Action

A GitHub Action that automatically generates a beautiful summary table of Python wheel builds across all platforms and Python versions.

## Features

- **Completely generic** - Works with any Python project that builds wheels
- **Zero configuration** - Automatically detects platforms and Python versions from wheel filenames
- **PEP 427 compliant** - Parses standard wheel naming convention
- **Smart sorting** - Platforms and Python versions are sorted logically
- **Free-threaded support** - Detects Python 3.14t and other free-threaded builds
- **PyPy support** - Recognizes PyPy wheels
- **All platforms** - Linux (manylinux, musllinux), Windows (x64, x86, ARM64), macOS (x86_64, ARM64, Universal2)

## Example Output

The action generates a summary table like this:

| Platform | 3.8 | 3.9 | 3.10 | 3.11 | 3.12 | 3.13 | 3.14 | 3.14t | PyPy3.9 |
|----------|-----|-----|------|------|------|------|------|-------|---------|
| **Linux x86_64** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | - | ✅ |
| **Linux aarch64** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | - | - |
| **musllinux x86_64** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | - | - |
| **Windows x64** | - | - | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | - |
| **Windows x86** | - | - | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | - |
| **Windows ARM64** | - | - | - | ✅ | ✅ | ✅ | ✅ | ✅ | - |
| **macOS x86_64** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **macOS ARM64** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

## Usage

### Basic Usage

```yaml
- name: Download artifacts
  uses: actions/download-artifact@v4
  with:
    pattern: wheels-*
    path: wheels

- name: Generate build summary
  uses: patrick91/wheels-ci-action@v1
  with:
    wheels-path: wheels
```

### Complete Example

Here's a complete workflow example for a Python package using `maturin`:

```yaml
name: Build

on: [push, pull_request]

jobs:
  build-linux:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        target: [x86_64, aarch64]
    steps:
      - uses: actions/checkout@v4
      - name: Build wheels
        uses: PyO3/maturin-action@v1
        with:
          target: ${{ matrix.target }}
          args: --release --out dist
      - name: Upload wheels
        uses: actions/upload-artifact@v4
        with:
          name: wheels-linux-${{ matrix.target }}
          path: dist

  build-windows:
    runs-on: windows-latest
    strategy:
      matrix:
        target: [x64, x86]
    steps:
      - uses: actions/checkout@v4
      - name: Build wheels
        uses: PyO3/maturin-action@v1
        with:
          target: ${{ matrix.target }}
          args: --release --out dist
      - name: Upload wheels
        uses: actions/upload-artifact@v4
        with:
          name: wheels-windows-${{ matrix.target }}
          path: dist

  summary:
    name: Build Summary
    runs-on: ubuntu-latest
    if: always()
    needs: [build-linux, build-windows]
    steps:
      - name: Download all artifacts
        uses: actions/download-artifact@v4
        with:
          pattern: wheels-*
          path: all-wheels
      
      - name: Generate build summary
        uses: patrick91/wheels-ci-action@v1
        with:
          wheels-path: all-wheels
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `wheels-path` | Path to the directory containing wheel files (.whl). Can be nested in subdirectories. | No | `wheels` |

## How It Works

The action:

1. Recursively scans the specified directory for `.whl` files
2. Parses each wheel filename according to [PEP 427](https://peps.python.org/pep-0427/)
3. Extracts platform and Python version information
4. Generates a markdown table showing the build matrix
5. Writes the table to `$GITHUB_STEP_SUMMARY`

### Wheel Filename Parsing

The action follows the standard wheel naming convention:

```
{distribution}-{version}(-{build})?-{python}-{abi}-{platform}.whl
```

For example:
- `mypackage-1.0.0-cp312-cp312-manylinux_2_17_x86_64.whl`
- `mypackage-1.0.0-cp314t-cp314t-win_amd64.whl`
- `mypackage-1.0.0-pp39-pypy39_pp73-macosx_11_0_arm64.whl`

### Supported Platforms

The action automatically detects and categorizes:

- **Linux**: manylinux (all versions), generic linux
- **musllinux**: All versions
- **Windows**: x64 (amd64), x86 (32-bit), ARM64
- **macOS**: x86_64 (Intel), ARM64 (Apple Silicon), Universal2
- **Architectures**: x86_64, x86, aarch64, armv7, ppc64le, s390x

### Supported Python Versions

- **CPython**: 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14
- **Free-threaded**: 3.13t, 3.14t
- **PyPy**: PyPy3.7, PyPy3.8, PyPy3.9, PyPy3.10, PyPy3.11

## Why This Action?

Building Python wheels for multiple platforms is complex. You might use:
- `cibuildwheel` for pure Python packages
- `maturin` for Rust extensions
- `scikit-build` for C/C++ extensions

Regardless of your build tool, you end up with many wheel files across different jobs. This action provides a single, unified view of what was built, making it easy to verify your build matrix at a glance.

## License

MIT

## Contributing

Contributions welcome! This action is designed to be generic and work with any Python project.
