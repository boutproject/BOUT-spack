from spack_repo.builtin.build_systems.python import PythonPackage
from spack.package import depends_on, version

class PyXhermes(PythonPackage):
    """xHermes is a post-processing package for Hermes-3 in 1D, 2D and 3D which provides automatic conversion to SI units and many useful plotting routines."""

    homepage = "https://github.com/boutproject/xhermes"
    git = "https://github.com/boutproject/xhermes.git"

    # Set a maintainer if submitting this package to the spack repo
    # maintainers("github_user1", "github_user2")

    # Release version git tags
    tagged_versions = [
        "0.1.0",
        "0.1.1",
        "0.2.0",
    ]
    for v in tagged_versions:
        version(v, tag=f"v{v}")

    # Treat intermediate versions, mapped to specific Git commits, as release candidates ('rc' suffixes)
    #  - Can be used internally or by consuming packages when inter-release changes break something
    #  - By convention, commit hashes point to master; i.e. the commit where the breaking change was merged in
    #  - If the next release version isn't known - increment the last release version by 0.0.1
    # Format (don't change the line below, as it is used in CI to update package versions!)
    #   version("<next_release_version>rc<date_in_YYYYMMDD>", commit="<git_hash>")
    version("0.1.2rc20260610", commit="cf59f47018a390b847693b426f10365502684984")
    version("0.1.2rc20260611", commit="f29a8be90820afded0e32c00ec971d9d78ca8d4b")

    # Point at latest master/main branch
    version("master", branch="main")

    # Compatible Python versions
    depends_on("python@3.9:", type=("build", "run"))

    # Build dependencies
    depends_on("py-setuptools", type="build")

    # Runtime dependencies
    depends_on("py-xbout", type=("build", "run"))
    depends_on("py-xarray", type=("build", "run"))
