# Copyright 2013-2024 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack_repo.builtin.build_systems.python import PythonPackage
from spack.package import depends_on, version, conflicts


class PyXbout(PythonPackage):
    """xBOUT provides an interface for collecting the output data from a BOUT++ simulation into an xarray dataset in an efficient and scalable way, as well as accessor methods for common BOUT++ analysis and plotting tasks."""

    homepage = "https://github.com/boutproject/xBOUT"
    git = "https://github.com/boutproject/xbout.git"

    # Set a maintainer if submitting this package to the spack repo
    # maintainers("github_user1", "github_user2")

    # license("Apache-2.0")

    # Release version git tags
    tagged_versions = [
        "0.3.0",
        "0.3.1",
        "0.3.2",
        "0.3.3",
        "0.3.4",
        "0.3.5",
        "0.3.6",
        "0.3.7",
        "0.3.8",
        "0.4.0",
    ]

    for v in tagged_versions:
        version(v, tag=f"v{v}")

    # Treat intermediate versions, mapped to specific Git commits, as release candidates ('rc' suffixes)
    #  - Can be used internally or by consuming packages when inter-release changes break something
    #  - By convention, commit hashes point to master; i.e. the commit where the breaking change was merged in
    #  - If the next release version isn't known - increment the last release version by 0.0.1
    # Format (don't change the line below, as it is used in CI to update package versions!)
    #   version("<next_release_version>rc<date_in_YYYYMMDD>", commit="<git_hash>")
    version("0.4.0rc20250925", commit="9c634a4492cd480f9883151b4f89b9d22f607727") # netcdf4=>h5netcdf
    version("0.4.0rc20260211", commit="afac4967c662e1c75b549bf585e15a6330548d8c") # h5py


    # Point at latest master/main branch
    version("master", branch="master")

    # Compatible Python versions
    depends_on("python@3.9:", type=("build", "run"))

    # Build dependencies
    depends_on("py-setuptools@65:", type="build")
    depends_on("py-setuptools-scm@7:+toml", type="build")
    depends_on("py-wheel@0.29.0:", type="build")

    # Runtime dependencies
    depends_on("py-animatplot-ng@0.4.2:", type=("build", "run"))
    #depends_on("py-boutdata@0.1.4:", type=("build", "run"))
    depends_on("py-dask@2.10.0:+array", type=("build", "run"))
    depends_on("py-gelidum@0.5.3:", type=("build", "run"))
    depends_on("py-h5py", type=("build", "run"), when="@0.4.0rc20260211:")
    depends_on("py-h5netcdf", type=("build", "run"), when="@0.4.0rc20250925:")
    depends_on("py-matplotlib@3.3.3:", type=("build", "run"))
    depends_on("py-natsort@5.5.0:", type=("build", "run"))
    depends_on("py-netcdf4@1.4.0:", type=("build", "run"), when="@:0.3.8")
    depends_on("py-pillow@6.1.0:", type=("build", "run"))
    depends_on("py-xarray@2023.01.0:", type=("build", "run"))

    # Avoid LLVM dependency through pandas performance variant
    conflicts("py-pandas+performance", msg="pandas performance variant pulls in LLVM via numba")

    def config_settings(self, spec, prefix):
        settings = {}
        return settings
