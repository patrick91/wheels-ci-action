#!/usr/bin/env python3
"""
Generate a build summary table for Python wheel builds.

This action parses wheel filenames to extract platform and Python version information,
making it completely generic and reusable across projects.

Wheel naming convention (PEP 491):
{distribution}-{version}(-{build})?-{python}-{abi}-{platform}.whl

Example: rignore-0.2.0-cp312-cp312-macosx_11_0_arm64.whl
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WheelInfo:
    """Parsed wheel file information."""

    python_tag: str
    abi_tag: str
    platform_tag: str

    @property
    def python_version(self) -> str:
        """Extract human-readable Python version from python tag."""
        # Free-threaded Python (e.g., cp314t in python_tag or abi_tag)
        # Check python_tag first
        if match := re.match(r"cp(\d)(\d+)t", self.python_tag):
            major, minor = match.groups()
            return f"{major}.{minor}t"

        # Check abi_tag for free-threaded (e.g., cp314-cp314t)
        if match := re.match(r"cp(\d)(\d+)t", self.abi_tag):
            major, minor = match.groups()
            return f"{major}.{minor}t"

        # CPython (e.g., cp312, cp38)
        if match := re.match(r"cp(\d)(\d+)", self.python_tag):
            major, minor = match.groups()
            return f"{major}.{minor}"

        # PyPy (e.g., pp39, pp310)
        if match := re.match(r"pp(\d)(\d+)", self.python_tag):
            major, minor = match.groups()
            return f"PyPy{major}.{minor}"

        return self.python_tag

    @property
    def platform_name(self) -> str:
        """Extract human-readable platform name from platform tag."""
        platform = self.platform_tag.lower()

        # macOS (e.g., macosx_11_0_arm64, macosx_10_9_x86_64)
        if platform.startswith("macosx"):
            if "arm64" in platform or "aarch64" in platform:
                return "macOS ARM64"
            elif "x86_64" in platform or "intel" in platform:
                return "macOS x86_64"
            elif "universal2" in platform:
                return "macOS Universal2"
            return "macOS"

        # Windows (e.g., win_amd64, win32, win_arm64)
        if platform.startswith("win"):
            if "amd64" in platform or "x64" in platform:
                return "Windows x64"
            elif "arm64" in platform or "aarch64" in platform:
                return "Windows ARM64"
            elif "32" in platform or "x86" in platform:
                return "Windows x86"
            return "Windows"

        # Linux manylinux (e.g., manylinux_2_17_x86_64, manylinux2014_aarch64)
        if "manylinux" in platform:
            arch = self._extract_arch(platform)
            return f"Linux {arch}"

        # Linux musllinux (e.g., musllinux_1_1_x86_64, musllinux_1_2_aarch64)
        if "musllinux" in platform:
            arch = self._extract_arch(platform)
            return f"musllinux {arch}"

        # Generic Linux
        if "linux" in platform:
            arch = self._extract_arch(platform)
            return f"Linux {arch}"

        return platform

    def _extract_arch(self, platform: str) -> str:
        """Extract architecture from platform string."""
        # Common architecture patterns
        if "x86_64" in platform or "amd64" in platform:
            return "x86_64"
        if "aarch64" in platform or "arm64" in platform:
            return "aarch64"
        if "armv7" in platform or "armv7l" in platform:
            return "armv7"
        if "ppc64le" in platform:
            return "ppc64le"
        if "s390x" in platform:
            return "s390x"
        if "i686" in platform or "x86" in platform or "i386" in platform:
            return "x86"

        return "unknown"


def parse_wheel_filename(filename: str) -> WheelInfo | None:
    """
    Parse a wheel filename according to PEP 427.

    Format: {distribution}-{version}(-{build})?-{python}-{abi}-{platform}.whl
    """
    if not filename.endswith(".whl"):
        return None

    # Remove .whl extension
    name = filename[:-4]

    # Split by '-' and get the last 3 parts (python-abi-platform)
    parts = name.split("-")
    if len(parts) < 5:  # Need at least: name, version, python, abi, platform
        return None

    # Last 3 parts are python, abi, platform
    python_tag = parts[-3]
    abi_tag = parts[-2]
    platform_tag = parts[-1]

    return WheelInfo(python_tag=python_tag, abi_tag=abi_tag, platform_tag=platform_tag)


def scan_wheels(wheels_path: Path) -> tuple[dict[str, set[str]], set[str], set[str]]:
    """
    Scan all wheel files and build a matrix of platform -> versions.

    Returns:
        - matrix: Dict mapping platform to set of Python versions
        - platforms: Set of all platforms found
        - versions: Set of all Python versions found
    """
    matrix = defaultdict(set)
    platforms = set()
    versions = set()

    # Find all .whl files
    for wheel_file in wheels_path.rglob("*.whl"):
        filename = wheel_file.name

        wheel_info = parse_wheel_filename(filename)
        if not wheel_info:
            continue

        platform = wheel_info.platform_name
        version = wheel_info.python_version

        platforms.add(platform)
        versions.add(version)
        matrix[platform].add(version)

    return matrix, platforms, versions


def sort_platforms(platforms: set[str]) -> list[str]:
    """Sort platforms in a logical order (OS, then architecture)."""
    # Define order for OSes
    os_order = {
        "Linux": 0,
        "musllinux": 1,
        "Windows": 2,
        "macOS": 3,
    }

    # Define order for architectures
    arch_order = {
        "x86_64": 0,
        "x86": 1,
        "ARM64": 2,
        "aarch64": 3,
        "armv7": 4,
        "s390x": 5,
        "ppc64le": 6,
        "Universal2": 7,
    }

    def platform_sort_key(platform: str) -> tuple[int, int, str]:
        # Split platform into OS and architecture
        parts = platform.split(" ", 1)
        os_name = parts[0]
        arch = parts[1] if len(parts) > 1 else ""

        return (os_order.get(os_name, 99), arch_order.get(arch, 99), platform)

    return sorted(platforms, key=platform_sort_key)


def sort_versions(versions: set[str]) -> list[str]:
    """Sort Python versions in logical order."""

    def version_sort_key(version: str) -> tuple[int, int, int, int]:
        # Handle PyPy versions
        if version.startswith("PyPy"):
            match = re.match(r"PyPy(\d+)\.(\d+)", version)
            if match:
                major, minor = match.groups()
                return (1, int(major), int(minor), 0)  # PyPy comes after CPython

        # Handle free-threaded versions (e.g., 3.14t)
        if version.endswith("t"):
            match = re.match(r"(\d+)\.(\d+)t", version)
            if match:
                major, minor = match.groups()
                return (0, int(major), int(minor), 1)  # FT comes after regular

        # Handle regular CPython versions
        match = re.match(r"(\d+)\.(\d+)", version)
        if match:
            major, minor = match.groups()
            return (0, int(major), int(minor), 0)

        return (99, 0, 0, 0)

    return sorted(versions, key=version_sort_key)


def generate_table(matrix: dict[str, set[str]], platforms: set[str], versions: set[str]) -> str:
    """Generate the markdown table."""
    lines = []

    # Header
    lines.append("# Build Summary - All Platforms and Architectures")
    lines.append("")

    # Sort platforms and versions
    sorted_platforms = sort_platforms(platforms)
    sorted_versions = sort_versions(versions)

    # Table header
    header = "| Platform | " + " | ".join(sorted_versions) + " |"
    separator = "|----------|" + "|".join(["-----"] * len(sorted_versions)) + "|"

    lines.append(header)
    lines.append(separator)

    # Table rows
    for platform in sorted_platforms:
        row = f"| **{platform}** |"
        for version in sorted_versions:
            if version in matrix[platform]:
                row += " ✅ |"
            else:
                row += " - |"
        lines.append(row)

    return "\n".join(lines)


def parse_version_requirement(requirement: str, available_versions: set[str]) -> list[str]:
    """
    Parse version requirement string into list of versions.

    Supports:
    - Single versions: "3.12" -> ["3.12"]
    - Ranges: "3.10-3.13" -> ["3.10", "3.11", "3.12", "3.13"]
    - Open-ended: "3.10+" -> ["3.10", "3.11", ...] (limited by available versions + 1)
    - PyPy single: "PyPy3.9" -> ["PyPy3.9"]
    - PyPy ranges: "PyPy3.9-3.11" -> ["PyPy3.9", "PyPy3.10", "PyPy3.11"]
    - PyPy open-ended: "PyPy3.9+" -> ["PyPy3.9", "PyPy3.10", ...] (limited by available)
    """
    requirement = requirement.strip()

    # Handle PyPy versions
    if requirement.startswith("PyPy"):
        # Handle PyPy open-ended ranges (e.g., "PyPy3.9+")
        if requirement.endswith("+"):
            start = requirement[:-1].strip()
            if match := re.match(r"PyPy(\d+)\.(\d+)", start):
                major, minor_start = map(int, match.groups())

                # Find the highest available PyPy version
                max_minor = minor_start
                for ver in available_versions:
                    if ver_match := re.match(r"PyPy(\d+)\.(\d+)", ver):
                        ver_major, ver_minor = map(int, ver_match.groups())
                        if ver_major == major and ver_minor > max_minor:
                            max_minor = ver_minor

                # Generate PyPy versions from start to max available + 1
                return [f"PyPy{major}.{minor}" for minor in range(int(minor_start), max_minor + 2)]

        # Handle PyPy ranges (e.g., "PyPy3.9-3.11")
        if "-" in requirement and requirement.count("-") == 1 and requirement.index("-") > 4:
            start_part, end = requirement.split("-", 1)
            start_match = re.match(r"PyPy(\d+)\.(\d+)", start_part.strip())
            end_match = re.match(r"(\d+)\.(\d+)", end.strip())
            if start_match and end_match:
                major, minor_start = map(int, start_match.groups())
                _, minor_end = map(int, end_match.groups())
                return [
                    f"PyPy{major}.{minor}" for minor in range(int(minor_start), int(minor_end) + 1)
                ]

        # Single PyPy version
        return [requirement]

    # Handle CPython open-ended ranges (e.g., "3.10+")
    if requirement.endswith("+"):
        start = requirement[:-1].strip()
        if match := re.match(r"(\d+)\.(\d+)", start):
            major, minor_start = map(int, match.groups())

            # Find the highest available version to determine upper bound
            max_minor = minor_start
            for ver in available_versions:
                if ver_match := re.match(r"(\d+)\.(\d+)", ver):
                    ver_major, ver_minor = map(int, ver_match.groups())
                    if ver_major == major and ver_minor > max_minor:
                        max_minor = ver_minor

            # Generate versions from start to max available + 1 (to allow checking for next version)
            return [f"{major}.{minor}" for minor in range(int(minor_start), max_minor + 2)]

    # Handle CPython ranges (e.g., "3.10-3.13")
    if "-" in requirement:
        start, end = requirement.split("-", 1)
        start_match = re.match(r"(\d+)\.(\d+)", start.strip())
        end_match = re.match(r"(\d+)\.(\d+)", end.strip())
        if start_match and end_match:
            major, minor_start = map(int, start_match.groups())
            _, minor_end = map(int, end_match.groups())
            return [f"{major}.{minor}" for minor in range(int(minor_start), int(minor_end) + 1)]

    # Single version
    return [requirement]


def validate_requirements(
    matrix: dict[str, set[str]],
    platforms: set[str],
    versions: set[str],
    require_platforms: str,
    require_python_versions: str,
    require_freethreaded: str,
    require_matrix: str,
) -> tuple[bool, list[str]]:
    """
    Validate that required wheels are present.

    Supports both simple global requirements and per-platform matrix requirements.
    If require_matrix is specified, it takes precedence over global requirements.

    Returns:
        Tuple of (all_requirements_met, list_of_errors)
    """
    errors = []

    # If matrix requirements are specified, use those exclusively
    if require_matrix:
        try:
            # Try to parse as JSON first
            matrix_requirements = json.loads(require_matrix)
        except json.JSONDecodeError:
            errors.append(f"Invalid JSON in require-matrix: {require_matrix}")
            return False, errors

        # Validate each platform requirement in the matrix
        for req in matrix_requirements:
            platform_pattern = req.get("platform", "")
            required_versions_str = req.get("versions", "")

            if not platform_pattern:
                continue

            # Find matching platforms (supports wildcards)
            matching_platforms = [p for p in platforms if fnmatch.fnmatch(p, platform_pattern)]

            if not matching_platforms:
                errors.append(f"No platforms found matching pattern: {platform_pattern}")
                continue

            # Parse required versions for this platform
            required_versions_raw = [
                v.strip() for v in required_versions_str.split(",") if v.strip()
            ]
            required_versions = []
            for version_req in required_versions_raw:
                required_versions.extend(parse_version_requirement(version_req, versions))

            # Check each matching platform for the required versions
            for platform in matching_platforms:
                platform_versions = matrix.get(platform, set())
                missing = [v for v in required_versions if v not in platform_versions]
                if missing:
                    errors.append(
                        f"Platform '{platform}' missing required versions: {', '.join(missing)}"
                    )

        return len(errors) == 0, errors

    # Fall back to simple global validation if no matrix specified
    # Validate required platforms
    if require_platforms:
        required_platforms = [p.strip() for p in require_platforms.split(",") if p.strip()]
        missing_platforms = [p for p in required_platforms if p not in platforms]
        if missing_platforms:
            errors.append(f"Missing required platforms: {', '.join(missing_platforms)}")

    # Validate required Python versions (globally across all platforms)
    if require_python_versions:
        required_versions_raw = [v.strip() for v in require_python_versions.split(",") if v.strip()]
        required_versions = []
        for req in required_versions_raw:
            required_versions.extend(parse_version_requirement(req, versions))

        # Only check versions that could exist (filter by what's reasonable)
        missing_versions = [
            v for v in required_versions if v not in versions and not v.endswith("t")
        ]
        if missing_versions:
            errors.append(f"Missing required Python versions: {', '.join(missing_versions)}")

    # Validate free-threaded requirements (globally)
    if require_freethreaded and require_freethreaded != "none":
        [v for v in versions if v.endswith("t")]

        if require_freethreaded == "3.14":
            if "3.14t" not in versions:
                errors.append("Missing required free-threaded Python 3.14t")

        elif require_freethreaded == "3.14+":
            # Check for 3.14t and any future versions
            if "3.14t" not in versions:
                errors.append("Missing required free-threaded Python 3.14t")

        elif require_freethreaded == "all":
            # Check that all regular versions also have free-threaded builds
            regular_versions = [
                v for v in versions if not v.endswith("t") and not v.startswith("PyPy")
            ]
            for version in regular_versions:
                ft_version = f"{version}t"
                if ft_version not in versions:
                    errors.append(
                        f"Missing free-threaded build for Python {version} (expected {ft_version})"
                    )

    return len(errors) == 0, errors


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate wheel build summary")
    parser.add_argument("wheels_path", help="Path to directory containing wheel files")
    parser.add_argument(
        "--require-platforms", default="", help="Comma-separated list of required platforms"
    )
    parser.add_argument(
        "--require-python-versions",
        default="",
        help="Comma-separated list of required Python versions",
    )
    parser.add_argument(
        "--require-freethreaded", default="none", help="Free-threaded build requirements"
    )
    parser.add_argument(
        "--require-matrix",
        default="",
        help="JSON string defining per-platform version requirements",
    )
    parser.add_argument(
        "--fail-on-missing", default="true", help="Whether to fail on missing wheels"
    )
    parser.add_argument(
        "--output-file",
        default="",
        help="Optional file to write the summary to (in addition to GITHUB_STEP_SUMMARY)",
    )

    args = parser.parse_args()
    wheels_path = Path(args.wheels_path)

    if not wheels_path.exists():
        print(f"Error: Path '{wheels_path}' does not exist", file=sys.stderr)
        sys.exit(1)

    # Scan wheels and build matrix
    matrix, platforms, versions = scan_wheels(wheels_path)

    if not platforms or not versions:
        print("No wheel files found", file=sys.stderr)
        sys.exit(1)

    # Validate requirements
    requirements_met, errors = validate_requirements(
        matrix,
        platforms,
        versions,
        args.require_platforms,
        args.require_python_versions,
        args.require_freethreaded,
        args.require_matrix,
    )

    # Generate markdown table
    table = generate_table(matrix, platforms, versions)

    # Add validation results to table if there are errors
    if errors:
        table += "\n\n## ⚠️ Missing Required Wheels\n\n"
        for error in errors:
            table += f"- ❌ {error}\n"

    # Write to GitHub step summary
    if github_step_summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(github_step_summary, "a") as f:
            f.write(table + "\n")
    else:
        # For local testing
        print(table)

    # Write to output file if specified (for PR comments)
    if args.output_file:
        with open(args.output_file, "w") as f:
            f.write(table + "\n")

    # Exit with error if requirements not met and fail-on-missing is true
    if not requirements_met and args.fail_on_missing.lower() == "true":
        print("❌ Required wheels are missing!", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)
    elif not requirements_met:
        print("⚠️ Warning: Required wheels are missing, but continuing...", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)


if __name__ == "__main__":
    main()
