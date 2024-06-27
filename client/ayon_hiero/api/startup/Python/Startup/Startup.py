import traceback

# activate hiero from pype
from ayon_core.pipeline import install_host
from ayon_core.hosts.hiero.api import HieroHost

host = HieroHost()
install_host(host)

try:
    __import__("ayon_hiero.api")
    __import__("pyblish")

except ImportError as e:
    print(traceback.format_exc())
    print("pyblish: Could not load integration: %s " % e)

else:
    # Setup integration
    import ayon_hiero.api as phiero
    phiero.lib.setup()
