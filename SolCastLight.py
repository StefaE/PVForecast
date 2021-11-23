import os
import sys
import argparse
import configparser
from datetime import datetime
from PVForecast.solcast import SolCast

if __name__ == "__main__":
    cfgParser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cfgParser.add_argument('-c', '--cfg', help="Specify config file (default: ./solcast_light_config.ini)", metavar="FILE")
    args = cfgParser.parse_args()
    if args.cfg: cfgFile = args.cfg
    else:        cfgFile = 'solcast_light_config.ini'

    try:
        config = configparser.ConfigParser(inline_comment_prefixes='#', empty_lines_in_values=False)
        if not os.path.isfile(cfgFile): raise Exception ('File does not exist')
        config.read(cfgFile)
    except Exception as e:
        print("Error reading config file '" + cfgFile + "': " + str(e))
        sys.exit(1)

    print("------------------------- Start (" + cfgFile + ")")
    mySolCast = SolCast(config)
    mySolCast.getSolCast()
    print("------------------------- End: " + datetime.now().strftime("%Y-%m-%d, %H:%M:%S"))