import cudf

from optimus.bumblebee import Comm
from optimus.engines.base.create import Create
from optimus.engines.base.engine import BaseEngine
from optimus.engines.cudf.cudf import CUDF
from optimus.engines.cudf.io.load import Load
from optimus.profiler.profiler import Profiler
from optimus.version import __version__
from dask import dataframe as dd

CUDF.instance = None
Profiler.instance = None
Comm.instance = None


class CUDFEngine(BaseEngine):
    __version__ = __version__

    def __init__(self, verbose=False, comm=None, *args, **kwargs):
        if comm is True:
            Comm.instance = Comm()
        else:
            Comm.instance = comm

        self.engine = 'cudf'

        self.create = Create(cudf)
        self.load = Load()
        self.verbose(verbose)

        CUDF.instance = cudf

        self.client = CUDF.instance

        Profiler.instance = Profiler()
        self.profiler = Profiler.instance


