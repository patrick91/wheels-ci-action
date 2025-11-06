"""Tests for generate_summary module."""

from pathlib import Path

import pytest
from inline_snapshot import external, register_format_alias

from generate_summary import (
    WheelInfo,
    generate_table,
    parse_version_requirement,
    parse_wheel_filename,
    scan_wheels,
    sort_platforms,
    sort_versions,
    validate_requirements,
)

# Register .md format as an alias to .txt for markdown files
register_format_alias(".md", ".txt")


class TestWheelInfo:
    """Test WheelInfo dataclass."""

    def test_python_version_cpython(self) -> None:
        wheel = WheelInfo(python_tag="cp312", abi_tag="cp312", platform_tag="linux_x86_64")
        assert wheel.python_version == "3.12"

    def test_python_version_freethreaded(self) -> None:
        wheel = WheelInfo(python_tag="cp314t", abi_tag="cp314t", platform_tag="linux_x86_64")
        assert wheel.python_version == "3.14t"

    def test_python_version_freethreaded_abi_only(self) -> None:
        """Test freethreaded wheels where 't' is only in abi_tag (e.g., cp314-cp314t)."""
        wheel = WheelInfo(python_tag="cp314", abi_tag="cp314t", platform_tag="linux_x86_64")
        assert wheel.python_version == "3.14t"

    def test_python_version_pypy(self) -> None:
        wheel = WheelInfo(python_tag="pp39", abi_tag="pypy39_pp73", platform_tag="linux_x86_64")
        assert wheel.python_version == "PyPy3.9"

    def test_platform_name_macos_arm64(self) -> None:
        wheel = WheelInfo(python_tag="cp312", abi_tag="cp312", platform_tag="macosx_11_0_arm64")
        assert wheel.platform_name == "macOS ARM64"

    def test_platform_name_macos_x86_64(self) -> None:
        wheel = WheelInfo(python_tag="cp312", abi_tag="cp312", platform_tag="macosx_10_9_x86_64")
        assert wheel.platform_name == "macOS x86_64"

    def test_platform_name_windows_x64(self) -> None:
        wheel = WheelInfo(python_tag="cp312", abi_tag="cp312", platform_tag="win_amd64")
        assert wheel.platform_name == "Windows x64"

    def test_platform_name_windows_x86(self) -> None:
        wheel = WheelInfo(python_tag="cp312", abi_tag="cp312", platform_tag="win32")
        assert wheel.platform_name == "Windows x86"

    def test_platform_name_windows_arm64(self) -> None:
        wheel = WheelInfo(python_tag="cp312", abi_tag="cp312", platform_tag="win_arm64")
        assert wheel.platform_name == "Windows ARM64"

    def test_platform_name_linux_manylinux(self) -> None:
        wheel = WheelInfo(python_tag="cp312", abi_tag="cp312", platform_tag="manylinux_2_17_x86_64")
        assert wheel.platform_name == "Linux x86_64"

    def test_platform_name_musllinux(self) -> None:
        wheel = WheelInfo(python_tag="cp312", abi_tag="cp312", platform_tag="musllinux_1_1_x86_64")
        assert wheel.platform_name == "musllinux x86_64"


class TestParseWheelFilename:
    """Test parse_wheel_filename function."""

    def test_parse_valid_wheel(self) -> None:
        result = parse_wheel_filename("rignore-0.2.0-cp312-cp312-macosx_11_0_arm64.whl")
        assert result is not None
        assert result.python_tag == "cp312"
        assert result.abi_tag == "cp312"
        assert result.platform_tag == "macosx_11_0_arm64"

    def test_parse_freethreaded_wheel(self) -> None:
        result = parse_wheel_filename("mypackage-1.0.0-cp314t-cp314t-win_amd64.whl")
        assert result is not None
        assert result.python_tag == "cp314t"
        assert result.python_version == "3.14t"

    def test_parse_pypy_wheel(self) -> None:
        result = parse_wheel_filename("mypackage-1.0.0-pp39-pypy39_pp73-linux_x86_64.whl")
        assert result is not None
        assert result.python_tag == "pp39"
        assert result.python_version == "PyPy3.9"

    def test_parse_invalid_extension(self) -> None:
        result = parse_wheel_filename("notawheel.tar.gz")
        assert result is None

    def test_parse_invalid_format(self) -> None:
        result = parse_wheel_filename("invalid.whl")
        assert result is None


class TestScanWheels:
    """Test scan_wheels function."""

    @pytest.fixture
    def temp_wheels(self, tmp_path: Path) -> Path:
        """Create temporary wheel files for testing."""
        wheels_dir = tmp_path / "wheels"
        wheels_dir.mkdir()

        # Create some test wheel files
        (wheels_dir / "pkg-1.0.0-cp312-cp312-manylinux_2_17_x86_64.whl").touch()
        (wheels_dir / "pkg-1.0.0-cp312-cp312-win_amd64.whl").touch()
        (wheels_dir / "pkg-1.0.0-cp313-cp313-manylinux_2_17_x86_64.whl").touch()
        (wheels_dir / "pkg-1.0.0-cp314t-cp314t-macosx_11_0_arm64.whl").touch()
        (wheels_dir / "pkg-1.0.0-pp39-pypy39_pp73-linux_x86_64.whl").touch()

        return wheels_dir

    def test_scan_wheels(self, temp_wheels: Path) -> None:
        matrix, platforms, versions = scan_wheels(temp_wheels)

        # Check platforms
        assert "Linux x86_64" in platforms
        assert "Windows x64" in platforms
        assert "macOS ARM64" in platforms

        # Check versions
        assert "3.12" in versions
        assert "3.13" in versions
        assert "3.14t" in versions
        assert "PyPy3.9" in versions

        # Check matrix
        assert "3.12" in matrix["Linux x86_64"]
        assert "3.13" in matrix["Linux x86_64"]
        assert "3.12" in matrix["Windows x64"]
        assert "3.14t" in matrix["macOS ARM64"]


class TestSortPlatforms:
    """Test sort_platforms function."""

    def test_sort_platforms(self) -> None:
        platforms = {
            "macOS ARM64",
            "Windows x64",
            "Linux x86_64",
            "musllinux x86_64",
            "Linux aarch64",
            "Windows ARM64",
        }

        sorted_list = sort_platforms(platforms)

        # Linux should come first
        assert sorted_list[0].startswith("Linux")
        # musllinux after Linux
        assert any(p.startswith("musllinux") for p in sorted_list[: len(sorted_list) // 2])
        # macOS should be last
        assert sorted_list[-1].startswith("macOS") or sorted_list[-2].startswith("macOS")


class TestSortVersions:
    """Test sort_versions function."""

    def test_sort_versions(self) -> None:
        versions = {"3.12", "3.8", "3.14t", "PyPy3.9", "3.10", "3.14"}

        sorted_list = sort_versions(versions)

        # Should be in order: 3.8, 3.10, 3.12, 3.14, 3.14t, PyPy3.9
        assert sorted_list == ["3.8", "3.10", "3.12", "3.14", "3.14t", "PyPy3.9"]


class TestGenerateTable:
    """Test generate_table function with inline-snapshot."""

    def test_generate_simple_table(self) -> None:
        """Test generating a simple markdown table."""
        matrix = {
            "Linux x86_64": {"3.12", "3.13"},
            "Windows x64": {"3.12"},
            "macOS ARM64": {"3.13", "3.14t"},
        }
        platforms = {"Linux x86_64", "Windows x64", "macOS ARM64"}
        versions = {"3.12", "3.13", "3.14t"}

        result = generate_table(matrix, platforms, versions)

        assert result == external("uuid:b9b6d8f7-2145-4f52-aad8-b5ec38a5bbbf.md")

    def test_generate_complex_table(self) -> None:
        """Test generating a complex table with many platforms and versions."""
        matrix = {
            "Linux x86_64": {"3.8", "3.9", "3.10", "3.11", "3.12", "3.13", "PyPy3.9"},
            "Linux aarch64": {"3.10", "3.11", "3.12", "3.13"},
            "musllinux x86_64": {"3.10", "3.11", "3.12"},
            "Windows x64": {"3.10", "3.11", "3.12", "3.13", "3.14", "3.14t"},
            "Windows x86": {"3.10", "3.11"},
            "Windows ARM64": {"3.11", "3.12", "3.13"},
            "macOS x86_64": {"3.8", "3.9", "3.10", "3.11", "3.12", "3.13", "3.14", "PyPy3.9"},
            "macOS ARM64": {"3.10", "3.11", "3.12", "3.13", "3.14", "3.14t"},
        }
        platforms = set(matrix.keys())
        versions = {
            "3.8",
            "3.9",
            "3.10",
            "3.11",
            "3.12",
            "3.13",
            "3.14",
            "3.14t",
            "PyPy3.9",
        }

        result = generate_table(matrix, platforms, versions)

        assert result == external("uuid:2862b59e-e298-4351-9094-91218ff7c1f8.md")

    def test_generate_empty_table(self) -> None:
        """Test generating a table with no builds."""
        matrix: dict[str, set[str]] = {}
        platforms: set[str] = set()
        versions: set[str] = set()

        result = generate_table(matrix, platforms, versions)

        assert result == external("uuid:233401cd-22d1-4cae-9bb3-49b8edebcec8.md")


class TestParseVersionRequirement:
    """Test parse_version_requirement function."""

    def test_single_version(self) -> None:
        available = {"3.12", "3.13", "3.14"}
        result = parse_version_requirement("3.12", available)
        assert result == ["3.12"]

    def test_version_range(self) -> None:
        available = {"3.12", "3.13", "3.14"}
        result = parse_version_requirement("3.10-3.13", available)
        assert result == ["3.10", "3.11", "3.12", "3.13"]

    def test_open_ended_range(self) -> None:
        available = {"3.12", "3.13", "3.14"}
        result = parse_version_requirement("3.12+", available)
        # Should generate up to max available + 1
        assert result == ["3.12", "3.13", "3.14", "3.15"]

    def test_pypy_single_version(self) -> None:
        available = {"PyPy3.9", "PyPy3.10", "PyPy3.11"}
        result = parse_version_requirement("PyPy3.9", available)
        assert result == ["PyPy3.9"]

    def test_pypy_range(self) -> None:
        available = {"PyPy3.9", "PyPy3.10", "PyPy3.11"}
        result = parse_version_requirement("PyPy3.9-3.11", available)
        assert result == ["PyPy3.9", "PyPy3.10", "PyPy3.11"]

    def test_pypy_open_ended_range(self) -> None:
        available = {"PyPy3.9", "PyPy3.10", "PyPy3.11"}
        result = parse_version_requirement("PyPy3.9+", available)
        # Should generate up to max available + 1
        assert result == ["PyPy3.9", "PyPy3.10", "PyPy3.11", "PyPy3.12"]


class TestValidateRequirements:
    """Test validate_requirements function."""

    def test_all_requirements_met(self) -> None:
        matrix = {"Linux x86_64": {"3.12", "3.13", "3.14t"}}
        platforms = {"Linux x86_64"}
        versions = {"3.12", "3.13", "3.14", "3.14t"}

        success, errors = validate_requirements(
            matrix, platforms, versions,
            require_platforms="Linux x86_64",
            require_python_versions="3.12,3.13",
            require_freethreaded="3.14",
            require_matrix="",
        )

        assert success is True
        assert errors == []

    def test_missing_platform(self) -> None:
        matrix = {"Linux x86_64": {"3.12"}}
        platforms = {"Linux x86_64"}
        versions = {"3.12"}

        success, errors = validate_requirements(
            matrix, platforms, versions,
            require_platforms="Linux x86_64,Windows x64",
            require_python_versions="",
            require_freethreaded="none",
            require_matrix="",
        )

        assert success is False
        assert len(errors) == 1
        assert "Windows x64" in errors[0]

    def test_missing_python_version(self) -> None:
        matrix = {"Linux x86_64": {"3.12", "3.13"}}
        platforms = {"Linux x86_64"}
        versions = {"3.12", "3.13"}

        success, errors = validate_requirements(
            matrix, platforms, versions,
            require_platforms="",
            require_python_versions="3.12,3.13,3.14",
            require_freethreaded="none",
            require_matrix="",
        )

        assert success is False
        assert len(errors) == 1
        assert "3.14" in errors[0]

    def test_missing_freethreaded(self) -> None:
        matrix = {"Linux x86_64": {"3.14"}}
        platforms = {"Linux x86_64"}
        versions = {"3.14"}

        success, errors = validate_requirements(
            matrix, platforms, versions,
            require_platforms="",
            require_python_versions="",
            require_freethreaded="3.14",
            require_matrix="",
        )

        assert success is False
        assert len(errors) == 1
        assert "3.14t" in errors[0]

    def test_freethreaded_all(self) -> None:
        matrix = {"Linux x86_64": {"3.12", "3.13", "3.14t"}}
        platforms = {"Linux x86_64"}
        versions = {"3.12", "3.13", "3.14", "3.14t"}

        success, errors = validate_requirements(
            matrix, platforms, versions,
            require_platforms="",
            require_python_versions="",
            require_freethreaded="all",
            require_matrix="",
        )

        assert success is False
        assert len(errors) == 2  # Missing 3.12t, 3.13t (3.14 has 3.14t)
        assert "3.12t" in errors[0] or "3.12t" in errors[1]
        assert "3.13t" in errors[0] or "3.13t" in errors[1]

    def test_matrix_validation_exact_match(self) -> None:
        matrix = {
            "Linux x86_64": {"3.12", "3.13", "3.14t", "PyPy3.9"},
            "Windows x64": {"3.12"},
        }
        platforms = {"Linux x86_64", "Windows x64"}
        versions = {"3.12", "3.13", "3.14t", "PyPy3.9"}

        require_matrix_json = '[{"platform": "Linux x86_64", "versions": "3.12,3.13,3.14t"}, {"platform": "Windows x64", "versions": "3.12"}]'

        success, errors = validate_requirements(
            matrix, platforms, versions,
            require_platforms="",
            require_python_versions="",
            require_freethreaded="none",
            require_matrix=require_matrix_json,
        )

        assert success is True
        assert errors == []

    def test_matrix_validation_with_wildcard(self) -> None:
        matrix = {
            "Linux x86_64": {"3.12", "3.13"},
            "Linux aarch64": {"3.12", "3.13"},
            "Windows x64": {"3.12"},
        }
        platforms = {"Linux x86_64", "Linux aarch64", "Windows x64"}
        versions = {"3.12", "3.13"}

        require_matrix_json = '[{"platform": "Linux*", "versions": "3.12,3.13"}, {"platform": "Windows*", "versions": "3.12"}]'

        success, errors = validate_requirements(
            matrix, platforms, versions,
            require_platforms="",
            require_python_versions="",
            require_freethreaded="none",
            require_matrix=require_matrix_json,
        )

        assert success is True
        assert errors == []

    def test_matrix_validation_missing_version(self) -> None:
        matrix = {
            "Linux x86_64": {"3.12"},
            "Windows x64": {"3.12"},
        }
        platforms = {"Linux x86_64", "Windows x64"}
        versions = {"3.12"}

        require_matrix_json = '[{"platform": "Linux x86_64", "versions": "3.12,3.13"}, {"platform": "Windows x64", "versions": "3.12"}]'

        success, errors = validate_requirements(
            matrix, platforms, versions,
            require_platforms="",
            require_python_versions="",
            require_freethreaded="none",
            require_matrix=require_matrix_json,
        )

        assert success is False
        assert len(errors) == 1
        assert "Linux x86_64" in errors[0]
        assert "3.13" in errors[0]
