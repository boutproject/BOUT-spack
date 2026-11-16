"""Shared helper functions for reading and updating Spack packages."""

from pathlib import Path
import re

from spack.repo import Repo, PATH


def get_pkg_classes(pkg_names, namespace="bout"):
    """
    Read classes from the package repo.
    """
    repo_path = Path(__file__).resolve().parent.parent / "spack_repo" / namespace
    local_repo = Repo(
        str(repo_path),
        cache=PATH.repos[0]._cache,
    )
    return {pkg_name: local_repo.get_pkg_class(pkg_name) for pkg_name in pkg_names}


def is_release_tag(tag):
    """
    Check if a git tag has the form of a release version (vX.Y.Z or X.Y.Z, where X, Y, and Z are integers).
    """
    pattern = r"^v?\d+\.\d+\.\d+$"
    return re.match(pattern, tag) is not None


def read_pkg_files(pkg_classes):
    """
    Read package.py for each package in the <pkg_classes> dict and return the contents in another dict.
    """
    pkgs_content = {}
    for pkg_name, pkg_class in pkg_classes.items():
        pkgfile = Path(pkg_class.package_dir) / "package.py"
        if not pkgfile.exists():
            print(
                f"WARNING: Package file for {pkg_name} not found at [{pkgfile}]!? Skipping."
            )
            continue
        pkgs_content[pkg_name] = pkgfile.read_text()
    return pkgs_content
