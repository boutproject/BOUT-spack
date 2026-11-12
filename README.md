# BOUT++ Spack repository

Contains [Spack](https://github.com/spack/spack) packages related to
the BOUT++ project.

To use this, first [install Spack](https://spack.readthedocs.io/en/latest/getting_started.html#installation). Then clone this repository and add
it to your spack repository list:

    git clone https://github.com/boutproject/BOUT-spack.git
    spack repo add BOUT-spack

Additional packages should now be available.

## Formatting

[Ruff](https://docs.astral.sh/ruff/) is used to format all Python source, including Spack package
recipes and CI scripts. To set up a pre-commit hook that runs Ruff automatically, install
[uv](https://docs.astral.sh/uv/getting-started/installation/), ensure it's on your `PATH`, then run these commands from the repository root:

```sh
uv sync --project dev --only-dev
uv run --project dev --no-sync prek install
```
If the hook reformats any files, you'll need to stage the formatting changes, then commit again.
Note that `prek` and `ruff` get installed in `dev/.venv`.

To update Ruff, change its version in `dev/pyproject.toml`, run `uv lock --project dev` to regenerate the uv lock file, then commit the changes to both files.

### Useful commands

- Format all Python files manually: `uv run --project dev --only-dev ruff format .`
- Check formatting without changing files: `uv run --project dev --only-dev ruff format --check .`
- Run the pre-commit hook manually: `uv run --project dev --no-sync prek run --all-files`
