from spack_repo.builtin.build_systems.python import PythonPackage
from spack.package import depends_on, version

class PyXhermes(PythonPackage):
    """xHermes is a post-processing package for Hermes-3 in 1D, 2D and 3D which provides automatic conversion to SI units and many useful plotting routines."""

    homepage = "https://github.com/boutproject/xhermes"
    pypi = "xhermes/xhermes-0.1.0.tar.gz"
    git      = "https://github.com/boutproject/xbout.git"

    # Set a maintainer if submitting this package to the spack repo
    # maintainers("github_user1", "github_user2")

    # PyPI versions with checksums
    version(
        "0.1.0",
        sha256="3aa0ba60d06cd18adfc46132f1d8deb3cd4ce69e67ee210d491bdfd7ba7871a7",
    )
    version(
        "0.1.1",
        sha256="93440969181f6269955faa8ddb0818589df33e555736eb75fda39fef76092cad",
    )

    # Point at latest master/main branch
    version("master", branch="main")

    # Compatible Python versions
    depends_on("python@3.9:", type=("build", "run"))

    # Build dependencies
    depends_on("py-setuptools", type="build")

    # Runtime dependencies
    depends_on("py-xbout", type=("build", "run"))
    depends_on("py-xarray", type=("build", "run"))
