# Example Configuration for Rignore

Based on your build matrix, here's the recommended configuration:

```yaml
summary:
  name: Build Summary
  runs-on: ubuntu-latest
  if: always()
  needs: [linux, musllinux, windows, windows-x64-freethreaded, windows-x86-freethreaded, windows-arm, windows-arm-freethreaded, macos]
  steps:
    - uses: actions/checkout@v4
    - name: Download all artifacts
      uses: actions/download-artifact@v4
      with:
        pattern: wheels-*
        path: all-wheels
    
    - name: Generate build summary with validation
      uses: patrick91/wheels-ci-action@main
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

This will:
- ✅ Require all Python versions 3.8-3.14 + 3.14t + PyPy 3.9-3.11 on Linux, musllinux, and macOS
- ✅ Require Python 3.8-3.14 + 3.14t on Windows x64 and x86 (no PyPy)
- ✅ Require only Python 3.11-3.14 + 3.14t on Windows ARM64 (newer platform)
- ✅ Fail the build if any required wheels are missing
- ✅ Show detailed error messages for what's missing

## Alternative: Simple Mode

If you want to just ensure minimum coverage without being too strict:

```yaml
- name: Generate build summary
  uses: patrick91/wheels-ci-action@main
  with:
    wheels-path: all-wheels
    require-python-versions: "3.8-3.14"
    require-freethreaded: "3.14"
```

This requires at least 3.8-3.14 and 3.14t to exist somewhere (but doesn't require them on every platform).
