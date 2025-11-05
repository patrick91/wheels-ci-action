#!/usr/bin/env python3
"""
Generate a build summary table for Python wheel builds.

This action parses wheel filenames to extract platform and Python version information,
making it completely generic and reusable across projects.

Wheel naming convention (PEP 491):
{distribution}-{version}(-{build})?-{python}-{abi}-{platform}.whl

Example: rignore-0.2.0-cp312-cp312-macosx_11_0_arm64.whl
"""

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
        # Free-threaded Python (e.g., cp314t)
        if match := re.match(r"cp(\d)(\d+)t", self.python_tag):
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

    def platform_sort_key(platform: str):
        # Split platform into OS and architecture
        parts = platform.split(" ", 1)
        os_name = parts[0]
        arch = parts[1] if len(parts) > 1 else ""

        return (os_order.get(os_name, 99), arch_order.get(arch, 99), platform)

    return sorted(platforms, key=platform_sort_key)


def sort_versions(versions: set[str]) -> list[str]:
    """Sort Python versions in logical order."""

    def version_sort_key(version: str):
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


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: generate_summary.py <wheels-path>", file=sys.stderr)
        sys.exit(1)

    wheels_path = Path(sys.argv[1])

    if not wheels_path.exists():
        print(f"Error: Path '{wheels_path}' does not exist", file=sys.stderr)
        sys.exit(1)

    # Scan wheels and build matrix
    matrix, platforms, versions = scan_wheels(wheels_path)

    if not platforms or not versions:
        print("No wheel files found", file=sys.stderr)
        sys.exit(1)

    # Generate markdown table
    table = generate_table(matrix, platforms, versions)

    # Write to GitHub step summary
    if github_step_summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(github_step_summary, "a") as f:
            f.write(table + "\n")
    else:
        # For local testing
        print(table)


if __name__ == "__main__":
    main()
