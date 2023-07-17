#!/usr/bin/env python

from importlib import resources
import sys
from pathlib import Path


# Determine if we are in a local installation or in a system (or env-) installation (i.e. if pip was called with -e option or not):
prefix = resources.files("runflex")
if Path(sys.prefix) in prefix.parents :
    prefix = Path(sys.prefix).joinpath('share/flexpart')
else :
    prefix = prefix.parent
