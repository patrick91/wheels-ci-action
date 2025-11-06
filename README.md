# Wheels CI Action

A GitHub Action that automatically generates a beautiful summary table of Python wheel builds across all platforms and Python versions.

## Features

- **Completely generic** - Works with any Python project that builds wheels
- **Zero configuration** - Automatically detects platforms and Python versions from wheel filenames
- **PEP 491 compliant** - Parses standard wheel naming convention
- **Free-threaded support** - Detects Python 3.14t free-threaded builds
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

### With Validation

You can ensure specific wheels are built by adding validation:

```yaml
- name: Generate build summary
  uses: patrick91/wheels-ci-action@v1
  with:
    wheels-path: all-wheels
    require-platforms: "Linux x86_64,Windows x64,macOS ARM64"
    require-python-versions: "3.10-3.14"
    require-freethreaded: "3.14"
```

This will fail the workflow if any required wheels are missing, with a detailed error message showing what's missing.

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
| `require-platforms` | Comma-separated list of required platforms (e.g., `"Linux x86_64,Windows x64"`). If any are missing, the action will fail. Only used in simple mode. | No | `""` (no validation) |
| `require-python-versions` | Comma-separated list of required Python versions. Supports ranges like `"3.10-3.13"` or `"3.12+"`. Applied globally to all platforms in simple mode. | No | `""` (no validation) |
| `require-freethreaded` | Require free-threaded Python builds. Options: `"none"` (default), `"3.14"`, `"3.14+"`, `"all"`. Applied globally in simple mode. | No | `"none"` |
| `require-matrix` | JSON array defining per-platform version requirements. Each entry has `"platform"` (supports wildcards) and `"versions"` fields. When specified, takes precedence over simple mode settings. | No | `""` (use simple mode) |
| `fail-on-missing` | Whether to fail the action if required wheels are missing. Set to `"false"` to only warn. | No | `"true"` |

## Validation

The action can validate that required wheels are present and fail the build if any are missing. This is useful for catching build matrix issues early.

### Two Validation Modes

1. **Simple Mode**: Apply the same requirements globally across all platforms
2. **Matrix Mode**: Specify different requirements for different platforms (with wildcard support)

### Platform Validation

Specify exact platform names that must be present:

```yaml
require-platforms: "Linux x86_64,Windows x64,macOS ARM64"
```

### Python Version Validation

Supports several formats for both CPython and PyPy:

**CPython:**
- **Individual versions**: `"3.12,3.13,3.14"`
- **Ranges**: `"3.10-3.14"` (includes 3.10, 3.11, 3.12, 3.13, 3.14)
- **Open-ended**: `"3.12+"` (requires 3.12 and all newer versions currently available)

**PyPy:**
- **Individual versions**: `"PyPy3.9,PyPy3.10,PyPy3.11"`
- **Ranges**: `"PyPy3.9-3.11"` (includes PyPy3.9, PyPy3.10, PyPy3.11)
- **Open-ended**: `"PyPy3.9+"` (requires PyPy3.9 and all newer PyPy versions)

**Combined:**
```yaml
require-python-versions: "3.10-3.14,PyPy3.9-3.11"
```

Examples:
```yaml
require-python-versions: "3.10,3.11,3.12,3.13,3.14"
require-python-versions: "3.10-3.14"
require-python-versions: "3.12+"
require-python-versions: "3.12+,PyPy3.10+"
```

**Note**: CPython and PyPy are treated as separate interpreters. Specifying `"3.9"` will not match `"PyPy3.9"` - you must explicitly require PyPy versions if needed.

### Free-threaded Validation

Options for validating free-threaded Python builds:

- `"none"`: No free-threaded validation (default)
- `"3.14"`: Require Python 3.14t
- `"3.14+"`: Require 3.14t and all future free-threaded versions
- `"all"`: Every Python version must have a corresponding free-threaded build

```yaml
require-freethreaded: "3.14"  # Only require 3.14t
require-freethreaded: "all"   # Require 3.10t, 3.11t, 3.12t, etc.
```

### Matrix Mode (Per-Platform Requirements)

For more granular control, use `require-matrix` to specify different requirements for each platform. This is perfect when different platforms support different Python versions:

```yaml
- name: Generate build summary
  uses: patrick91/wheels-ci-action@v1
  with:
    wheels-path: all-wheels
    require-matrix: |
      [
        {
          "platform": "Linux*",
          "versions": "3.8-3.14,3.14t,PyPy3.9-3.11"
        },
        {
          "platform": "musllinux*",
          "versions": "3.8-3.14,3.14t,PyPy3.9-3.11"
        },
        {
          "platform": "macOS*",
          "versions": "3.8-3.14,3.14t,PyPy3.9-3.11"
        },
        {
          "platform": "Windows x64",
          "versions": "3.8-3.14,3.14t"
        },
        {
          "platform": "Windows x86",
          "versions": "3.8-3.14,3.14t"
        },
        {
          "platform": "Windows ARM64",
          "versions": "3.11-3.14,3.14t"
        }
      ]
```

**Features:**
- **Wildcards**: `"Linux*"` matches `"Linux x86_64"`, `"Linux aarch64"`, etc.
- **Per-platform versions**: Different platforms can require different Python versions
- **Full version support**: Ranges (`3.10-3.14`), open-ended (`3.12+`), PyPy (`PyPy3.9-3.11`)

**Note**: When `require-matrix` is specified, it takes precedence over `require-python-versions` and `require-freethreaded`.

### Warning Mode

Set `fail-on-missing: "false"` to only show warnings without failing:

```yaml
- name: Generate build summary
  uses: patrick91/wheels-ci-action@v1
  with:
    wheels-path: all-wheels
    require-python-versions: "3.10-3.14"
    fail-on-missing: "false"  # Only warn, don't fail
```

## How It Works

The action:

1. Recursively scans the specified directory for `.whl` files
2. Parses each wheel filename according to [PEP 491](https://peps.python.org/pep-0491/)
3. Extracts platform and Python version information
4. Validates against requirements (if specified)
5. Generates a markdown table showing the build matrix
6. Writes the table to `$GITHUB_STEP_SUMMARY`
7. Fails the build if validation errors are found (unless `fail-on-missing: "false"`)

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
- **Free-threaded**: 3.14t
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
