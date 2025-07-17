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
    git = "https://github.com/boutproject/hermes-3.git"

    maintainers("bendudson")

    license("GPL-3.0-or-later")

    version("develop", branch="develop")
    version("master", branch="master", submodules=True, preferred=True)
    version("1.3.1", tag="v1.3.1", submodules=True)
    version("1.3.0", tag="v1.3.0", submodules=True)
    version("1.2.1", tag="v1.2.1", submodules=True)
    version("1.2.0", tag="v1.2.0", submodules=True)

    variant(
        "limiter",
        default="MC",
        description="Slope limiter",
        values=("MC", "MinMod"),
        multi=False,
    )
    variant(
        "petsc",
        default=False,
        description="Builds boutpp dependency with PETSc support.",
    )
    variant(
        "sundials",
        default=True,
        description="Builds boutpp dependency with SUNDIALS support.",
    )
    variant(
        "xhermes", default=True, description="Builds xhermes (required for some tests)."
    )

    # Always-required dependencies
    # depends_on("adios2", type=("build", "link"))

    depends_on("cmake@3.24:", type="build")
    depends_on("fftw", type=("build", "link"))
    depends_on("mpi", type=("build", "link", "run"))
    depends_on("boutpp", type=("build", "link"))
    depends_on("netcdf-cxx4", type=("build", "link"))

    # Variant-controlled dependencies
    depends_on("petsc+hypre+mpi~debug~fortran", when="+petsc", type=("build", "link"))
    depends_on("py-xhermes", when="+xhermes", type=("run"))
    depends_on("sundials", when="+sundials", type=("build", "link"))

    def cmake_args(self):
        # Definitions controlled by variants
        variant_defs = {
            "HERMES_SLOPE_LIMITER": "limiter",
        }
        variant_args = [
            self.define_from_variant(def_str, var_str)
            for def_str, var_str in variant_defs.items()
        ]

        fixed_args = [self.define("HERMES_BUILD_BOUT", False)]

        # Concatenate different arg types and return
        args = []
        args.extend(fixed_args)
        args.extend(variant_args)

        return args
