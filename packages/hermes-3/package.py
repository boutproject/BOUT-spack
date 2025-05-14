# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack import *


class Hermes3(CMakePackage):
    """A multifluid magnetized plasma simulation model.

    Hermes-3 is built on the BOUT++ framework, and uses a system of reusable components
    to build models at runtime based on input configuration, in 1D, 2D or 3D curvlinear
    coordinates."""

    homepage = "https://hermes3.readthedocs.io/"
    url = "https://github.com/bendudson/hermes-3/archive/refs/tags/v1.1.0.tar.gz"
    git = "https://github.com/bendudson/hermes-3.git"

    maintainers("bendudson")

    license("GPL-3.0-or-later")

    # Note: Release tarballs don't include BOUT++ submodule
    #       so for releases specify the commit hash
    version("master", branch="master")
    version("1.3.0", commit="5be1525")
    version("1.2.1", commit="f1dadcc")
    version("1.2.0", commit="081c8cf")

    variant(
        "limiter",
        default="MC",
        description="Slope limiter",
        values=("MC", "MinMod"),
        multi=False,
    )
    variant("petsc", default=False, description="Builds with PETSc support.")
    variant("sundials", default=True, description="Builds with SUNDIALS support.")
    variant(
        "xhermes", default=True, description="Builds xhermes (required for some tests)."
    )

    # Always-required dependencies
    # depends_on("adios2", type=("build", "link", "run"))
    depends_on("cmake@3.24:", type="build")
    depends_on("fftw", type=("build", "link", "run"))
    depends_on("mpi", type=("build", "link", "run"))
    depends_on("netcdf-cxx4", type=("build", "link", "run"))
    # Should these be xhermes deps instead?
    depends_on("py-cython", type=("build", "link", "run"))
    depends_on("py-jinja2", type=("build", "link", "run"))
    depends_on("py-netcdf4", type=("build", "link", "run"))

    # Variant-controlled dependencies
    depends_on(
        "petsc+hypre+mpi~debug~fortran", when="+petsc", type=("build", "link", "run")
    )
    depends_on("py-xhermes", when="+xhermes", type=("build", "link", "run"))
    # Could add Sundials as a spack dependency here?
    # Download it via the BOUT cmake flag for now
    # depends_on("sundials", when="+sundials", type=("build", "link", "run"))

    def cmake_args(self):
        # Always build with Sundials.
        # Use variants to toggle other config options.
        return [
            self.define("BOUT_DOWNLOAD_SUNDIALS", True),
            self.define_from_variant("BOUT_USE_PETSC", "petsc"),
            self.define_from_variant("HERMES_SLOPE_LIMITER", "limiter"),
        ]
