"""Remove package release candidate (RC) versions that have been superseded by full releases."""

import argparse
import ast
from dataclasses import dataclass
import json
from pathlib import Path
import re

from spack.version import StandardVersion, Version

from package_utils import get_pkg_classes, is_release_tag, read_pkg_files


@dataclass(frozen=True)
class DependencySpec:
    """A data class to aggregate properties of a 'depends_on' statetment"""

    node: ast.Expr
    name: str
    version: StandardVersion
    is_rc: bool
    parent_version: StandardVersion
    variant: str


def get_dependency_spec(node, latest_releases):
    """
    If <node> has the form
      depends_on("dep_name@dep_version:", when="version_requirement")
    then return a DependencySpec with its parsed dependency and condition.
    Otherwise (i.e. if there's anything non-standard) return None, causing the node to be ignored.
    """
    # Must be a depends_on call with a constant string-type first arg
    if not is_call_with_const_arg(node, "depends_on", str):
        return None
    depends_on_str = node.value.args[0].value

    # Dependency string must include a version specifier and the dependency must have at least one full release
    dep_name, separator, _ = depends_on_str.partition("@")
    if not separator or latest_releases.get(dep_name) is None:
        return None

    # There has to be a 'when' condition with the standard format
    if len(node.value.args) != 1 or len(node.value.keywords) != 1:
        return None
    condition = node.value.keywords[0]
    if not (
        condition.arg == "when"
        and isinstance(condition.value, ast.Constant)
        and isinstance(condition.value.value, str)
    ):
        return None
    # Extract the package name and version from the depends_on string
    parsed_dependency = re.fullmatch(
        r"([\w-]+)@(\d+\.\d+\.\d+(?:rc\d+)?):", depends_on_str
    )
    if parsed_dependency is None:
        print(
            f"WARNING: Skipping unrecognized dependency format at line "
            f"{node.lineno}: {depends_on_str!r}"
        )
        return None
    # The condition must specify a minimum version and an optional variant.
    parsed_condition = re.fullmatch(
        r"@(\d+(?:\.\d+)+(?:rc\d+)?):((?: \+[\w-]+)?)", condition.value.value
    )
    if parsed_condition is None:
        return None
    # Construct and return a DependencySpec object containing the parsed information
    dep_name, dep_version = parsed_dependency.groups()
    parent_version, variant = parsed_condition.groups()
    return DependencySpec(
        node=node,
        name=dep_name,
        version=Version(dep_version),
        is_rc=bool(re.fullmatch(r"\d+\.\d+\.\d+rc\d+", dep_version)),
        parent_version=Version(parent_version),
        variant=variant,
    )


def is_call_with_const_arg(node, function_name, arg_type=None):
    """
    Check if an AST node represents a call to <function_name> with a constant first argument.
    If [arg_type] is provided, warn and return False if the constant has a different type.
    """
    if not (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == function_name
        and bool(node.value.args)
        and isinstance(node.value.args[0], ast.Constant)
    ):
        return False
    value = node.value.args[0].value

    # If the other conditions are met, but the type is wrong, print a warning and return False.
    if arg_type is not None and not isinstance(value, arg_type):
        print(
            f"WARNING: Skipping {function_name} call at line {node.lineno}: "
            f"expected first argument of type {arg_type}, "
            f"got {type(value).__name__}: {value!r}"
        )
        return False
    return True


def latest_release_version(versions):
    """Return the latest full release, if the package has one."""
    return max(
        (version for version in versions if is_release_tag(str(version))), default=None
    )


def remove_old_rc_dependencies(pkg_content, dependency_versions, hermes_versions):
    """
    Remove depends_on statements in the hermes-3 package that reference superseded RC versions.
    Calls are removed iff there exists a dependency with the same form of condition that references a newer full release of the dependency.
    """
    dependency_releases = {
        name: latest_release_version(versions)
        for name, versions in dependency_versions.items()
    }
    hermes_releases = [
        version
        for version in hermes_versions
        if re.fullmatch(r"\d+(?:\.\d+)+", str(version))
    ]
    lines = pkg_content.splitlines(keepends=True)
    removed_lines = set()
    # Iterate over all class nodes in the package
    for class_node in ast.parse(pkg_content).body:
        if not isinstance(class_node, ast.ClassDef):
            continue
        dependencies = []
        # Assemble a list of dependencies for this class
        # Iterate over all nodes in the class body (i.e. statements within the class), processing 'depends_on' calls
        for node in class_node.body:
            # Extract dependency name, version, and condition
            #  (returns None if the nodes isn't a depends_on, or has a format other than the one added by added by update_spack_packages.py)
            dependency_spec = get_dependency_spec(node, dependency_releases)
            if dependency_spec is not None:
                dependencies.append(dependency_spec)
        # Loop over dependencies and mark superseded RC versions for removal
        # An RC dependency is judged to be superseded only if a similar dependency exists for the same parent version or the next release
        for dependency in dependencies:
            if any(
                dependency_is_superseded(
                    dependency,
                    other,
                    dependency_releases[dependency.name],
                    hermes_releases,
                )
                for other in dependencies
            ):
                node = dependency.node
                removed_lines.update(range(node.lineno - 1, node.end_lineno))

    # Return the package content, filtering out 'depends_on' statements that reference superseded RC versions
    return "".join(line for index, line in enumerate(lines) if index not in removed_lines)


def remove_old_rc_versions(pkg_content, versions):
    """
    Remove RC version declarations from pkg_content if a newer full release exists.
    No other text in the package is modified.
    """

    # Get the latest release version. Bail out if no releases are defined.
    latest_release = latest_release_version(versions)
    if latest_release is None:
        return pkg_content

    # Loop through lines in the package, identifying RC versions to remove.
    lines = pkg_content.splitlines(keepends=True)
    removed_lines = set()
    for node in ast.walk(ast.parse(pkg_content)):
        # Only consider 'version' calls with a string argument.
        if not is_call_with_const_arg(node, "version", str):
            continue
        # Mark for removal if this is a superseded RC version.
        version = node.value.args[0].value
        if re.fullmatch(r"\d+\.\d+\.\d+rc\d+", version) and latest_release > Version(
            version
        ):
            removed_lines.update(range(node.lineno - 1, node.end_lineno))

    # Return the package content, filtering out the marked lines
    return "".join(line for index, line in enumerate(lines) if index not in removed_lines)


def dependency_is_superseded(dep1, dep2, dependency_release, hermes_releases):
    """Decide whether <dep2> can supersede an <dep1>."""
    # dep1 must be an RC version, dep2 must be a later release
    # dep1 and dep2 must have the same name and the same variant (or lack thereof)
    if not (
        dep1.is_rc
        and dep2.name == dep1.name
        and not dep2.is_rc
        and dep2.version > dep1.version
        and dependency_release > dep1.version
        and dep2.variant == dep1.variant
    ):
        return False
    # Get the next parent release version, if one exists
    next_release = min(
        (release for release in hermes_releases if release > dep1.parent_version),
        default=None,
    )
    # <dep2> must reference either the same version as <dep1> or the next release, if there is one
    return dep2.parent_version == dep1.parent_version or (
        next_release is not None and dep2.parent_version == next_release
    )


def main():
    # Extract the pinned commits from the provided JSON file.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commits_file", required=True)
    args = parser.parse_args()
    with open(args.commits_file) as commits_file:
        pinned_commits = json.load(commits_file)

    # For each package that has a pinned commit, identify the package class
    pkg_classes = get_pkg_classes(pinned_commits.keys())
    # Extract dependency versions
    dependency_versions = {
        name: pkg_class.versions
        for name, pkg_class in pkg_classes.items()
        if name != "hermes-3"
    }

    # Loop through all packages, removing superseded RC versions and overwriting any files that change.
    for pkg_name, content in read_pkg_files(pkg_classes).items():
        pkg_class = pkg_classes[pkg_name]
        # Remove superseded RC versions
        updated_content = remove_old_rc_versions(content, pkg_class.versions)
        # For hermes-3 only, also remove superseded RC *dependency* versions.
        if pkg_name == "hermes-3":
            updated_content = remove_old_rc_dependencies(
                updated_content, dependency_versions, pkg_class.versions
            )
        # Overwrite the package file if anything changed
        if updated_content != content:
            pkgfile = Path(pkg_class.package_dir) / "package.py"
            pkgfile.write_text(updated_content)
            print(f"Removed superseded release candidates from {pkg_name}.")


if __name__ == "__main__":
    main()
