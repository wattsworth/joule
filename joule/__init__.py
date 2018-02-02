
from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

from .client import *
from .client.base_module import yesno
from .utils.numpypipe import *
from .utils.time import now as time_now
