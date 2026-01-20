# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack_repo.builtin.build_systems.cmake import CMakePackage
from spack.error import InstallError
from spack.package import depends_on, license, maintainers, variant, version
import spack.repo


def check_pkg_available(_unused1, variant_name, _unused2, raise_on_notfound=True):
    """Validator function to check that packages (particularly 'Reactions') are known to spack."""
    if not spack.repo.PATH.exists(variant_name):
        if raise_on_notfound:
            err_msg = f"Package '{variant_name}' does not exist in any known package repository."
            if variant_name == "vantagereactions":
                err_msg += "\nNote that building hermes-3 with +vantagereactions currently requires spack to be pointed to the packages inside a local copy of the https://github.com/UKAEA-Edge-Code/VANTAGE-Reactions git repo."
            raise InstallError(err_msg)
        else:
            return False
    else:
        return True


def vantagereactions_pkg_available():
    return check_pkg_available("", "vantagereactions", "", raise_on_notfound=False)


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
        "xhermes", default=True, description="Builds xhermes (required for some tests)."
    )
    variant(
        "vantagereactions",
        default=False,
        description="Build Hermes-3 with VANTAGE-Reactions suppport.",
        validator=check_pkg_available,
    )

    depends_on("cmake@3.24:", type="build")
    depends_on("fftw", type=("build", "link"))
    depends_on("mpi", type=("build", "link", "run"))
    depends_on("boutpp", type=("build", "link"))
    depends_on("netcdf-cxx4", type=("build", "link"))
    depends_on("py-boutdata@0.3.0:", type=("run"))

    # Variant-controlled dependencies
    depends_on("py-xhermes", when="+xhermes", type=("run"))
    if vantagereactions_pkg_available():
        depends_on("vantagereactions", when="+vantagereactions", type=("build", "link"))

    def cmake_args(self):
        # Definitions controlled by variants
        variant_defs = {
            "HERMES_SLOPE_LIMITER": "limiter",
            "HERMES_USE_VANTAGE": "vantagereactions",
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
