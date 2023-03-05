"""
Copyright (C) 2022    Stefan Eichenberger   se_misc ... hotmail.com

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

This is the main script to run a simulation of PVForecasts if only SolCast
os used as a solcast provider. By default, config_solcast_light.ini in the 
local directory is the configuration file. But argument -c can
specify a different file.

The companion script PVForecasts.py is used as main script for the full 
version with a multitude of forecast providers.


Deprecation Note: 
-----------------
    This SolCastLight.py script is deprecated. 
    All functionality (including simplified installation and simplified config file)
    are now served by the main script PVForecasts.py
"""
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
    print("Deprecated -- use 'PVForecast.py -c solcast_light_config.ini' instead")
    mySolCast = SolCast(config)
    mySolCast.getSolCast()
    print("------------------------- End: " + datetime.now().strftime("%Y-%m-%d, %H:%M:%S"))