# Usage

## Compile flexpart

There are two main ways to compile the code:
1. via `runflex --compile --rc config.yaml` (can be combined with the `--footprints` option).
2. via `make build`.

The first option is typically made for compiling FLEXPART in a directory outside the *runflex* installation path (e.g. runflex is installed in */runflex*, and you work in a project */home/mpyproj*. Use `runflex --compile` to compile flexpart in that directory). The second option is meant for deploying runflex (and FLEXPART) on a new system. Under the hood, both options use the `runflex.compile.Flexpart` class.

When compiling with `runflex` (first option above), the relevant config file settings are:

* `paths.build`: where the code should be compiled
* `paths.makefile`: which makefile to use
* `paths.src`: where is the main source code
* `paths.extras`: where is the *extra* source code: source files in that folder overwrite those in the `path.src` folder (that enables having different source codes for different projects, e.g. a *dev* code and a *stable* one).

When compiling with `make` (second option), the four paths listed above are passed via the `--build`, `--makefile`, `--src` and `--extra` arguments of the `runflex/compile.py` script (called inside the *makefile*). The default *make* behaviour is to compile two branches of the code: one with `--extra` pointing to *src/extra* (compiled inside *build/flexpart/stable*), and one with `--extra` pointing to *src/dev* (compiled inside *build/flexpart/dev*).

## Compute footprints

`runflex --footprints --rc rcfile [options]`

## Singularity/Apptainer wrapper



# Settings