"""
Tests to check that stale RC versions and related dependencies are removed correctly.
"""

import importlib.util
from itertools import product
from pathlib import Path
import unittest

from spack.version import Version

# Allow the test to import the cleanup function
cleanup_import = importlib.util.spec_from_file_location(
    "remove_old_rc_versions",
    Path(__file__).resolve().parents[1] / "remove-old-rc_versions.py",
)
cleanup_module = importlib.util.module_from_spec(cleanup_import)
cleanup_import.loader.exec_module(cleanup_module)


class VersionCleanupTests(unittest.TestCase):
    """Tests for checking removal of superseded RC package versions."""

    def setUp(self):
        """Set up package declarations and version metadata that can be used in multiple tests."""
        branch = "master"
        tagged_versions = ["1.4.1", "1.5.0"]
        # A release version declared separately, outside the usual 'tagged_versions' list
        separate_release = "1.4.0"
        rc_versions = {
            "1.4.2rc20260615": "abc123",
            "1.5.1rc20261113": "def456",
        }
        self.prefix = f'class Package:\n    version("{branch}", branch="{branch}")\n'
        self.release_decls = (
            f'    version("{separate_release}", tag="v{separate_release}")\n'
            f"    tagged_versions = {tagged_versions!r}\n"
            "    for v in tagged_versions:\n"
            '        version(v, tag=f"v{v}")\n'
            "    # Intermediate versions\n"
        )
        self.older_rc_decl, self.newer_rc_decl = (
            f'    version("{version}", commit="{commit}")\n'
            for version, commit in rc_versions.items()
        )
        self.non_release_versions = {
            Version(version): {"commit": commit}
            for version, commit in rc_versions.items()
        }
        self.non_release_versions[Version(branch)] = {"branch": branch}
        self.versions = {
            **self.non_release_versions,
            Version(separate_release): {"tag": f"v{separate_release}"},
            **{Version(version): {"tag": f"v{version}"} for version in tagged_versions},
        }

    def test_only_older_rc_versions_are_removed(self):
        """Check that older RCs are removed, releases, newer RCs and surrounding text are preserved."""
        mpi_dependency = '    depends_on("mpi")\n'
        for multiline in (False, True):
            with self.subTest(multiline=multiline):
                older_rc_decl = self.older_rc_decl
                if multiline:
                    # Also test that declaring the older RC version over multiple lines works correctly
                    older_rc_decl = (
                        older_rc_decl.replace("version(", "version(\n        ")
                        .replace(", commit=", ",\n        commit=")
                        .replace(")\n", ",\n    )\n")
                    )
                content = (
                    self.prefix
                    + self.release_decls
                    + older_rc_decl
                    + self.newer_rc_decl
                    + mpi_dependency
                )
                # The older RC version should be removed
                expected = (
                    self.prefix + self.release_decls + self.newer_rc_decl + mpi_dependency
                )
                self.assertEqual(
                    cleanup_module.remove_old_rc_versions(content, self.versions),
                    expected,
                )
                # Running the cleanup function again should not change it
                self.assertEqual(
                    cleanup_module.remove_old_rc_versions(expected, self.versions),
                    expected,
                )

    def test_rc_versions_retained_without_full_release(self):
        """Check that all RC versions are retained when no full release is available."""
        content = self.prefix + self.older_rc_decl + self.newer_rc_decl
        self.assertEqual(
            cleanup_module.remove_old_rc_versions(content, self.non_release_versions),
            content,
        )


class DependencyCleanupTests(unittest.TestCase):
    """Tests for checking removal of dependency declarations that reference old RC versions."""

    def setUp(self):
        """Set up some package metadata to use in the tests."""

        # The package name, reference RC version and release version(s) for a dependency
        self.dep_name = "py-xhermes"
        self.orig_dep_version = "0.1.2rc20260611"
        self.dep_versions = {self.dep_name: [Version("0.2.0")]}

        # An RC version and variant of H3 that depends on the above dependency
        self.orig_H3_version = "1.4.2rc20260615"
        self.orig_H3_variant = "+xhermes"
        # H3 versions
        self.H3_version_tags = ["1.4.1", "1.5.0", "1.6.0"]
        self.H3_versions = {
            Version(version): {"tag": f"v{version}"} for version in self.H3_version_tags
        }
        self.H3_versions[Version(self.orig_H3_version)] = {"commit": "abc123"}

        # Package preamble for hermes-3
        self.H3_prefix = (
            "class Package:\n"
            f"    tagged_versions = {self.H3_version_tags!r}\n"
            "    for v in tagged_versions:\n"
            '        version(v, tag=f"v{v}")\n'
        )

        # Dependency spec
        self.orig_dep_spec = (
            f'    depends_on("{self.dep_name}@{self.orig_dep_version}:", '
            f'when="@{self.orig_H3_version}: {self.orig_H3_variant}")\n'
        )

        # Some other package name and version
        self.other_pkg_name = "other"
        self.other_pkg_version = "0.3.0"
        self.dep_versions[self.other_pkg_name] = [Version(self.other_pkg_version)]

    def clean(self, content):
        """Helper to apply the cleanup function"""
        return cleanup_module.remove_old_rc_dependencies(
            content, self.dep_versions, self.H3_versions
        )

    def test_rc_dep_retained_if_no_replacement_declared(self):
        """Check RC dependency version preserved when no alternative available"""
        # Include only the RC version of the dependency, with no alternative.
        content = self.H3_prefix + self.orig_dep_spec
        # The cleanup script should leave content unchanged.
        self.assertEqual(self.clean(content), content)

    def test_rc_dep_retained_if_replacement_unsuitable(self):
        """Check that unsuitable replacements for dependency RC versions are rejected."""
        # Various 'depends_on' statements that are NOT suitable replacements for the original RC dependency
        replacements = [
            # H3 version not specified
            f'depends_on("{self.dep_name}@0.2.0:", when="{self.orig_H3_variant}")',
            # Earlier H3 release
            f'depends_on("{self.dep_name}@0.2.0:", when="@1.4.1: {self.orig_H3_variant}")',
            # Different RC version of H3
            f'depends_on("{self.dep_name}@0.2.0:", when="@1.4.2rc20260616: {self.orig_H3_variant}")',
            # Undeclared release version of H3
            f'depends_on("{self.dep_name}@0.2.0:", when="@1.4.2: {self.orig_H3_variant}")',
            # Skips the next release of H3
            f'depends_on("{self.dep_name}@0.2.0:", when="@1.6.0: {self.orig_H3_variant}")',
            # Suitable version of H3 but different (missing) variant
            f'depends_on("{self.dep_name}@0.2.0:", when="@1.5.0:")',
            # Exact version of H3 specified, rather than a lower bound
            f'depends_on("{self.dep_name}@0.2.0:", when="@1.5.0 {self.orig_H3_variant}")',
            # Different platform in H3 spec
            f'depends_on("{self.dep_name}@0.2.0:", when="@{self.orig_H3_version}: {self.orig_H3_variant} platform=linux")',
            # Older dependency version
            f'depends_on("{self.dep_name}@0.1.1:", when="@{self.orig_H3_version}: {self.orig_H3_variant}")',
            # No dependency version
            f'depends_on("{self.dep_name}", when="@{self.orig_H3_version}: {self.orig_H3_variant}")',
            # RC dependency version rather than full release
            f'depends_on("{self.dep_name}@0.2.1rc20260727:", when="@{self.orig_H3_version}: {self.orig_H3_variant}")',
            # Extra keyword argument in depends_on declaration
            f'depends_on("{self.dep_name}@0.2.0:", when="@{self.orig_H3_version}: {self.orig_H3_variant}", type="run")',
            # Non-literal condition
            f'depends_on("{self.dep_name}@0.2.0:", when=some_condition)',
            # Unpacked keyword arguments
            f'depends_on("{self.dep_name}@0.2.0:", **options)',
            # Different dependency package name
            f'depends_on("{self.other_pkg_name}@{self.other_pkg_version}:", when="@{self.orig_H3_version}: {self.orig_H3_variant}")',
        ]
        for replacement in replacements:
            with self.subTest(replacement=replacement):
                content = (
                    self.H3_prefix + self.orig_dep_spec + "    " + replacement + "\n"
                )
                self.assertEqual(self.clean(content), content)

    def test_rc_dep_retained_if_no_later_release_exists(self):
        """Keep RC requirements until a newer full release exists."""
        # Construct package content containing both the original RC requirement and a potential replacement
        replacement = self.orig_dep_spec.replace(self.orig_dep_version, "0.2.0")
        content = self.H3_prefix + self.orig_dep_spec + replacement
        # Pass a versions dict that doesn't contain a full release newer than the RC
        versions = {self.dep_name: [Version("0.1.1"), Version("0.2.0rc1")]}
        # Expect that the cleanup function will not remove the RC requirement
        self.assertEqual(
            cleanup_module.remove_old_rc_dependencies(
                content, versions, self.H3_versions
            ),
            content,
        )

    def test_rc_dep_retained_if_replacement_nested(self):
        """Ignore potential replacements nested in blocks."""
        # Test that a depends_on inside an if block is ignored
        content_dep_in_ifblock = (
            self.H3_prefix
            + self.orig_dep_spec
            + f'    if enabled:\n        depends_on("{self.dep_name}@0.2.0:", '
            f'when="@{self.orig_H3_version}: {self.orig_H3_variant}")\n'
        )
        self.assertEqual(self.clean(content_dep_in_ifblock), content_dep_in_ifblock)

        # Test that a 'depends_on' inside an else block is ignored
        content_dep_in_elseblock = (
            self.H3_prefix
            + "    if enabled:\n"
            + "    "
            + self.orig_dep_spec
            + f'    else:\n        depends_on("{self.dep_name}@0.2.0:", '
            f'when="@{self.orig_H3_version}: {self.orig_H3_variant}")\n'
        )
        self.assertEqual(self.clean(content_dep_in_elseblock), content_dep_in_elseblock)

    def test_rc_removal(self):
        """
        Check cleanup function works and is idempotent.

        i.e. it should
          1. Remove the RC dependency on the first application
          2. Be a no-op on all subsequent applications
        """
        # Test removal with different versions, variant specifiers, and declaration formats
        for (
            H3_version,
            H3_variant,
            superseded_multiline,
            superseding_multiline,
        ) in product(
            (self.orig_H3_version, "1.5.0"),
            (f" {self.orig_H3_variant}", " +foo", ""),
            (False, True),
            (False, True),
        ):
            with self.subTest(
                H3_version=H3_version,
                H3_variant=H3_variant,
                superseded_multiline=superseded_multiline,
                superseding_multiline=superseding_multiline,
            ):
                # The 'depends_on' statement that has been superseded
                # (try the original variant, a different variant, and no variant)
                superseded = self.orig_dep_spec.replace(
                    f" {self.orig_H3_variant}", H3_variant
                )
                # The existing 'depends_on' statement that supersedes the other one
                # (Try different versions of H3 with a fixed dependency version)
                superseding = superseded.replace(self.orig_dep_version, "0.2.0").replace(
                    self.orig_H3_version, H3_version
                )
                # Also test that splitting the dependency declarations across multiple lines doesn't break anything
                superseded, superseding = (
                    declaration.replace("depends_on(", "depends_on(\n        ")
                    .replace(", when=", ",\n        when=")
                    .replace(")\n", ",\n    )\n")
                    if multiline
                    else declaration
                    for declaration, multiline in (
                        (superseded, superseded_multiline),
                        (superseding, superseding_multiline),
                    )
                )

                prefix = self.H3_prefix
                content = prefix + superseded + superseding
                expected_content = prefix + superseding
                self.assertEqual(self.clean(content), expected_content)
                self.assertEqual(self.clean(expected_content), expected_content)


if __name__ == "__main__":
    unittest.main()
