
# Paths
PLATFORM = $(shell grep ^ID= /etc/os-release | sed "s/ID=//" | sed 's/"//g')
FC = $(shell /usr/bin/nf-config --fc)
SRC_MAIN=src/flexpart10.4
SRC_EXTRA=src/extras
SRC_DEV=src/dev
BUILDDIR=build/flexpart
MAKEFILE=makefile.${PLATFORM}.${FC}


.PHONY: build
build:
	python -m pip install loguru
	python runflex/compile.py --build ${BUILDDIR}-stable --src ${SRC_MAIN} --extra ${SRC_EXTRA} --makefile ${MAKEFILE}
	python runflex/compile.py --build ${BUILDDIR}-dev --src ${SRC_MAIN} --extra ${SRC_DEV} --makefile ${MAKEFILE}

install:
	python -m pip install -e .[interactive]

clean:
	rm -Rf pyflex.egg-info
	rm -Rf build
	rm -f share/flexpart.x

uninstall:
	pip uninstall runflex

container:
	singularity build --fakeroot runflex.simg runflex.def

envcontainer:
	singularity build --fakeroot runflexenv.simg runflexenv.def
