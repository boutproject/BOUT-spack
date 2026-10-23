import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import spack.paths
from spack.repo import Repo, PATH
from spack.version import Version
from spack.fetch_strategy import GitFetchStrategy
from spack.version import infinity_versions

# script/global scope storage
_git_fetcher_cache = {}
_h3_variant_triggered_dependencies = {"py-xhermes": "xhermes"}
_repo_ref_cache = {}


# ============================== Helper classes ===============================
@dataclass
class GitRefMapper:
    """
    A data class that maps git references to commit hashes, storing an additional, separate mapping
    of tag->commit.
    """

    ref_to_commit: dict[str, str]
    tag_to_commit: dict[str, str]

    @classmethod
    def from_show_ref(cls, show_ref_output):
        """Build mappings from `git show-ref --dereference` output."""
        ref_to_commit = {}
        tag_refs = {}
        peeled_tag_refs = {}

        # Put heads straight into the (ref->commit) map, but discriminate between tags and 'peeled' tags
        for line in show_ref_output.splitlines():
            commit, ref = line.split()

            if ref.startswith("refs/heads/"):
                ref_to_commit[ref.removeprefix("refs/heads/")] = commit
            elif ref.startswith("refs/tags/"):
                short_ref = ref.removeprefix("refs/tags/")
                if short_ref.endswith("^{}"):
                    peeled_tag_refs[short_ref.removesuffix("^{}")] = commit
                else:
                    tag_refs[short_ref] = commit

        # Add tag refs to the map
        for tag_name, commit in tag_refs.items():
            ref_to_commit[tag_name] = commit
        # Add peeled tags to the map (overwrites regular tag refs)
        for tag_name, commit in peeled_tag_refs.items():
            ref_to_commit[tag_name] = commit

        # Return git ref->commit and tag->commit maps.
        return cls(
            ref_to_commit=ref_to_commit,
            tag_to_commit={tag: ref_to_commit[tag] for tag in tag_refs},
        )


# ==============================================================================


# ============================== Helper functions ==============================
def add_hermes_dependency(h3_content, h3_version, dep_name, dep_version):
    """
    Add a new depends_on(...) statement to the hermes-3 package.py file for [dep_name]@[dep_version].
    """

    # Find any 'depends_on' lines for <dep_name>
    dep_pattern = re.compile(
        rf'^\s*depends_on\("{re.escape(dep_name)}.*$',
        re.MULTILINE,
    )
    last_dep_match = None
    for match in dep_pattern.finditer(h3_content):
        last_dep_match = match

    # If no dependency exists (as is the case for py-xbout), it should be skipped
    if last_dep_match:
        insert_pos = last_dep_match.end()
        print(
            f"Adding new depends_on(...) for [{dep_name}]@[{dep_version}] to hermes-3 package.py"
        )
    else:
        print(
            f"[{dep_name}] isn't a direct dependency of hermes-3; depends_on(...) line won't be added."
        )
        return h3_content

    # Construct the 'depends_on' line
    # Specifies that hermes versions [h3_version] and onwards require [dep_name]@[dep_version] or higher
    dep_variant = _h3_variant_triggered_dependencies.get(dep_name, "")
    variant_str = f" +{dep_variant}" if dep_variant else ""
    new_dep_line = f'    depends_on("{dep_name}@{dep_version}:", when="@{h3_version}:{variant_str}")'
    h3_content = h3_content[:insert_pos] + "\n" + new_dep_line + h3_content[insert_pos:]
    return h3_content


# ------------------------------------------------------------------------------
def extract_version_commits(pkg_name, pkg_class):
    """
    Extract a dict of commit_hash-> {"version": version_str, "type": version_type} from the package class.
      version_type is one of "commit", "branch", "tag".
    """
    version_commits = {}
    for version, metadata in pkg_class.versions.items():
        # Skip spack "infinity" versions
        if str(version) in infinity_versions:
            continue

        commit = None
        vtype = "unknown"
        if "commit" in metadata:
            commit = metadata["commit"]
            vtype = "commit"
        else:
            for tag in ["branch", "tag"]:
                if tag in metadata:
                    # Try the reference first, then the version string, then "v" + version string
                    candidate_refs = [
                        metadata[tag],
                        str(version),
                        f"v{str(version)}",
                    ]
                    for ref in candidate_refs:
                        commit = get_git_ref_map(pkg_class).ref_to_commit.get(ref)
                        if commit is not None:
                            break
                if commit is not None:
                    vtype = tag
                    break

        if commit is None:
            print(
                f"WARNING: Unable to determine commit for {pkg_name}@{version}. Skipping."
            )
        else:
            version_commits[commit] = {"version": version.__str__(), "type": vtype}
    return version_commits


# ------------------------------------------------------------------------------
def get_git_ref_map(pkg_class):
    """
    Generate/retrieve a GitRefMapper for the [pkg_class], preferring a cached version if one exists.
    """

    # Return cached-refs if they already exist
    if pkg_class.git in _repo_ref_cache:
        return _repo_ref_cache[pkg_class.git]

    # Create a spack git-fetcher / retrieve cached version for the relevant repo
    if pkg_class.git not in _git_fetcher_cache:
        _git_fetcher_cache[pkg_class.git] = GitFetchStrategy(git=pkg_class.git)
    fetcher = _git_fetcher_cache[pkg_class.git]

    # Use spack machinery to bare-clone the repo into a cache directory
    repo_id = hashlib.sha1(pkg_class.git.encode("utf-8")).hexdigest()[:12]
    cache_dir = Path(spack.paths.user_repos_cache_path) / f"ci-version-cache-{repo_id}"
    if not cache_dir.exists():
        cache_dir.parent.mkdir(parents=True, exist_ok=True)
        fetcher.bare_clone(str(cache_dir))
    with working_directory(cache_dir):
        # Run fetch again to ensure refs in cached repo are up to date
        fetcher.git(
            "fetch",
            "--prune",
            "origin",
            "+refs/heads/*:refs/heads/*",
            "+refs/tags/*:refs/tags/*",
        )
        show_ref_output = fetcher.git(
            "show-ref",
            "--dereference",
            "--tags",
            "--heads",
            output=str,
        )

    result = GitRefMapper.from_show_ref(show_ref_output)

    # Cache the mapper
    _repo_ref_cache[pkg_class.git] = result

    return result


# ------------------------------------------------------------------------------
def add_missing_releases(pkg_name, pkg_class, pkg_content, version_commits):
    """Discover tagged release versions (independent of the current Hermes dependency pins) and add
    them to the package file if they don't already exist.

    Versions earlier than the minimum recorded in the package are assumed to be unsupported and are
    ignored. Add release commits (new and existing) to the version_commits map.

    N.B. If a version was previously recorded as a release candidate, but tagged later, the release
    version will overwrite it.
    """
    # Identify the oldest recorded release as the support floor.
    existing_releases = {
        str(version) for version in pkg_class.versions if is_release_tag(str(version))
    }
    # All packages should have at least one release
    if not existing_releases:
        raise RuntimeError(
            f"No release versions found for {pkg_name}; cannot determine support floor."
        )
    oldest_release = min(map(Version, existing_releases))

    # Get release tags and add any that aren't already in the package
    tags = get_git_ref_map(pkg_class).tag_to_commit
    release_tags = sorted(
        (tag for tag in tags if is_release_tag(tag)),
        key=lambda t: (Version(t.removeprefix("v")), t),
    )
    for tag in release_tags:
        release_version = tag.removeprefix("v")
        # Skip versions older than the support floor
        if Version(release_version) < oldest_release:
            continue
        # Add new version
        if release_version not in existing_releases:
            pkg_content, _ = insert_package_release_version(pkg_content, tag)
            existing_releases.add(release_version)
            print(
                f"ADDED release [{release_version}] of [{pkg_name}] from tag [{tag}]."
            )
        # Add the release commit to version_commits
        # Overwrite an existing entry if it's not a tag or if the discoverd release is newer.
        commit = tags[tag]
        previous = version_commits.get(commit)
        if (
            previous is None
            or previous["type"] != "tag"
            or Version(previous["version"]) < Version(release_version)
        ):
            version_commits[commit] = {"version": release_version, "type": "tag"}
    return pkg_content


# ------------------------------------------------------------------------------
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


# ------------------------------------------------------------------------------
def get_rc_version_tag(existing_versions):
    """
    Given a dict of existing versions, return the next rc version tag.
    """
    # Get major, minor, patch for the latest tagged release version
    tagged_release_versions = [
        commit_map["version"]
        for commit_map in existing_versions.values()
        if commit_map["type"] == "tag"
    ]
    if not tagged_release_versions:
        raise RuntimeError(
            "No released (tag/sha256) versions found; cannot derive next rc version."
        )
    latest_tagged_release_version = max(tagged_release_versions, key=Version)
    major, minor, patch = map(int, latest_tagged_release_version.split("."))

    # rc version is current version with patch incremented + "rcYYYYMMDD" suffix
    date_str = datetime.now().strftime("%Y%m%d")

    return f"{major}.{minor}.{patch + 1}rc{date_str}"


# ------------------------------------------------------------------------------
def insert_package_rc_version(pkg_content, existing_versions, new_version_commit):
    """
    Add a new RC version(...) line to package.py.
    """

    new_version = get_rc_version_tag(existing_versions)

    version_line = f'    version("{new_version}", commit="{new_version_commit}")'

    # This should never be true, but just in case...
    if new_version_commit in pkg_content:
        return pkg_content, new_version

    # Match RC version lines without consuming the newline after them.
    # Allow trailing comments
    rc_pattern = re.compile(
        r'^[ \t]*version\("\d+\.\d+\.\d+rc\d{8}".*?\)[ \t]*(?:#.*)?$',
        re.MULTILINE,
    )
    matches = list(rc_pattern.finditer(pkg_content))

    if matches:
        # Insert after the matched line break so the new version always lands on its own line.
        last = matches[-1]
        line_end = pkg_content.find("\n", last.end())
        insert_pos = line_end + 1 if line_end >= 0 else len(pkg_content)
    else:
        # Otherwise, insert on the first new line after the standardised RC version comment
        marker = "next_release_version"
        preamble_end_pos = pkg_content.find(marker)

        if preamble_end_pos < 0:
            raise RuntimeError("Could not find RC version preamble comment")

        insert_pos = pkg_content.find("\n", preamble_end_pos) + 1

    # Edge case where the new line is being inserted at EOF and the file has no trailing newline
    line_prefix = (
        "\n"
        if insert_pos == len(pkg_content) and not pkg_content.endswith("\n")
        else ""
    )

    return pkg_content[:insert_pos] + line_prefix + version_line + "\n" + pkg_content[
        insert_pos:
    ], new_version


# ------------------------------------------------------------------------------
def insert_package_release_version(pkg_content, tag):
    """
    Insert a new release version.
    (Add to the 'tagged_versions' or 'oldstyle_tagged_versions' lists in each package, as appropriate).
    """

    release_version = tag.removeprefix("v")

    # The tagged_versions loop assumes a leading 'v'; unprefixed tags use the oldstyle list.
    list_name = "tagged_versions" if tag.startswith("v") else "oldstyle_tagged_versions"

    # Locate the appropriate tagged_versions list
    pattern = re.compile(
        rf"(^[ \t]*{list_name}[ \t]*=[ \t]*\[)(.*?)(\])",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(pkg_content)
    if not match:
        if list_name == "oldstyle_tagged_versions":
            raise RuntimeError(
                "Release version string wasn't v-prefixed, and no alternative formats are supported in the package file."
            )
        raise RuntimeError("Could not find tagged_versions list")
    list_body = match.group(2)

    # Extract existing versions
    versions = re.findall(r'"([^"]+)"', list_body)

    if release_version in versions:
        return pkg_content, release_version

    versions.append(release_version)
    versions.sort(key=Version)

    new_body = "".join(f'\n        "{v}",' for v in versions)
    replacement = f"{match.group(1)}{new_body}\n    ]"

    return pkg_content[: match.start()] + replacement + pkg_content[
        match.end() :
    ], release_version


# ------------------------------------------------------------------------------
def is_release_tag(tag):
    """
    Check if a git tag has the form of a release version (vX.Y.Z or X.Y.Z, where X, Y, and Z are integers).
    """
    pattern = r"^v?\d+\.\d+\.\d+$"
    return re.match(pattern, tag) is not None


# ------------------------------------------------------------------------------
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


# ------------------------------------------------------------------------------
@contextmanager
def working_directory(path):
    old_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_cwd)


# =============================================================================
def main():

    # Read commits json
    parser = argparse.ArgumentParser()
    parser.add_argument("--commits_file", required=True)
    args = parser.parse_args()

    with open(args.commits_file) as f:
        pinned_commits = json.load(f)

    # Get all the package classes
    pkg_classes = get_pkg_classes(pinned_commits.keys())

    # Read all the package files
    all_content = read_pkg_files(pkg_classes)

    # Extract versions
    all_version_commits = {
        pkg_name: extract_version_commits(pkg_name, pkg_class)
        for pkg_name, pkg_class in pkg_classes.items()
    }

    # Keep track of commits that were already registered before new releases were added
    version_commits_excluding_new_releases = {
        pkg_name: set(version_commits)
        for pkg_name, version_commits in all_version_commits.items()
    }

    # Add any release versions that don't already exist in the package files.
    for pkg_name, pkg_class in pkg_classes.items():
        all_content[pkg_name] = add_missing_releases(
            pkg_name, pkg_class, all_content[pkg_name], all_version_commits[pkg_name]
        )

    # Separate the hermes commit; everything else is a dependency
    hermes_commit = pinned_commits.pop("hermes-3")

    # Add any new versions of dependencies to their respective package.py files
    new_dependency_versions = {}
    for dep_name, commit in pinned_commits.items():
        pkg_version_commits = all_version_commits.get(dep_name, {})
        if commit in pkg_version_commits:
            print(
                f"Commit [{commit}] of [{dep_name}] already registered as version [{pkg_version_commits[commit]['version']}]."
            )
            # Newly discovered releases have already been added to the package files, but
            # dependencies may still need to be updated.
            if commit not in version_commits_excluding_new_releases[dep_name]:
                new_dependency_versions[dep_name] = pkg_version_commits[commit][
                    "version"
                ]
        else:
            all_content[dep_name], dep_version = insert_package_rc_version(
                all_content[dep_name],
                pkg_version_commits,
                commit,
            )
            print(
                f"ADDED commit [{commit}] as version [{dep_version}] of [{dep_name}]."
            )
            new_dependency_versions[dep_name] = dep_version

    # Add depends_on(...) statements to the hermes package file if necessary
    if new_dependency_versions:
        existing_hermes_versions = all_version_commits["hermes-3"]
        if hermes_commit in existing_hermes_versions:
            # The pinned hermes commit is already registered in the package file
            hermes_version = existing_hermes_versions[hermes_commit]["version"]
        else:
            # The pinned hermes commit is new - insert that first before resolving dependencies
            # N.B. This also means it must be an rc version, releases have already been added
            print(f"Adding new hermes-3 version at commit [{hermes_commit}]")
            all_content["hermes-3"], hermes_version = insert_package_rc_version(
                all_content["hermes-3"],
                existing_hermes_versions,
                hermes_commit,
            )

        for dep_name, dep_version in new_dependency_versions.items():
            all_content["hermes-3"] = add_hermes_dependency(
                all_content["hermes-3"], hermes_version, dep_name, dep_version
            )

    # Write out all the modified package.py files
    for dep_name, content in all_content.items():
        pkgfile = Path(pkg_classes[dep_name].package_dir) / "package.py"
        pkgfile.write_text(content)


# =============================================================================

if __name__ == "__main__":
    main()
