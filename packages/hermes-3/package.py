# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack.package import *

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
    version("1.2.1", commit="f1dadcc")
    version("1.2.0", commit="081c8cf")

    variant("petsc", default=False, description="Enable PETSc solvers")
    variant(
        "limiter", default="MC", description="Slope limiter", values=("MC", "MinMod"), multi=False
    )

    depends_on("cmake", type="build")
    depends_on("mpi")
    depends_on("fftw")
    depends_on("netcdf-cxx4")
    depends_on("petsc+hypre+mpi", when="+petsc")

    def cmake_args(self):
        return [
            self.define("BOUT_DOWNLOAD_SUNDIALS", True),
            self.define_from_variant("HERMES_SLOPE_LIMITER", "limiter"),
        ]
