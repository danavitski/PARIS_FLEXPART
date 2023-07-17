# RUNFLEX

Runflex is a python library to run FLEXPART on a HPC cluster

### Content
* the _runflex_ folder contains the runflex python library itself
* the _bin_ folder contains the main executable (_runflex_)
* the _src_ folder contains the FLEXPART fortran code.
* the _inputs_ folder contains input files for FLEXPART runs (default COMMAND file, SPECIES_* files, default runflex settings (_defaults.yaml_) and some data files).

The root folder also contains singularity definition files, and a Makefile.

### Installation

For clarity below, the _runflex_ folder here designates the folder containing the _runflex_ python library, while the _root_ folder, designates the root of the git repository (i.e. the parent of _runflex_ folder).

#### Local installation
From the _root_ folder, just do `pip install [-e] .`. This should also install any missing python libraries (or just call `make install`).

#### as a _singularity_ container:
singularity (https://sylabs.io/singularity/) allows building a portable container for running the code. Two singularity definition files are provided:
- _runflex.def_ enables building a complete runflex container (containing runflex and a compiled version of FLEXPART).
- _runflexenv.def_ builds a container with the same run environment (libraries, paths, etc.) as _runflex.def_, but not including the actual _runflex_ and _FLEXPART_ codes (this avoids having to re-build the container at every change in the code, but requires mounting the source code in the container, as described below).

Assuming that singularity is installed on your system, build the first container with `make container`, or the second one with `make envcontainer`.

Use the containers with:
```
singularity run -B /path/to/meteo:/meteo -B /path/to/scratch:/scratch container.sif [options of bin/runfkex]
```

Here `container.sif` points to the container that was build before. If arguments/options of the _bin/runflex_ are provided, then that script is called within the container (with these options). Otherwise, it just opens a bash prompt inside the container.

If the container is built using runflexenv.def, the _root_ folder must be mounted under `/runflex` (e.g. add `-B /path/to/root:/runflex`) to the mount points.

### Use

The main script is _bin/runflex_. In the most typical case (computation of footprints for LUMIA), it is called with:
```
runflex --footprints --rc flexpart.yaml
```
`--rc` points to a configuration file in the yaml format. It sets in particular the various paths (`paths` section), the location of the observations file for which footprints should be computed, and the various FLEXPART settings (grid, species, output type, release length, etc.).