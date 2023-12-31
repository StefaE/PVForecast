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

This is the main script to run a simulation of PVForecasts. By default, 
config.ini in the local directory is the configuration file. But argument -c can
specify a different file.
"""

import argparse
from datetime import datetime
from PVForecast.forecast_manager import ForecastManager
from PVForecast.__init__ import __version__

if __name__ == "__main__":
    cfgParser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cfgParser.add_argument('-c', '--cfg', help="Specify config file (default: ./config.ini)", metavar="FILE")
    args = cfgParser.parse_args()
    if args.cfg: cfgFile = args.cfg
    else:        cfgFile = 'config.ini'
    print("--v" + __version__ + "-"*(22 - len(__version__)) + " Start (" + cfgFile + " at " + datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + " - local)")
    myForecastManager = ForecastManager(cfgFile)
    myForecastManager.runForecasts()
    print("------------------------- End (" + datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + " - local)")