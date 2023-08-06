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
"""

import pandas as pd
import configparser
import sys
import os
from datetime import datetime, timezone, timedelta

from .dwdforecast    import DWDForecast
from .openweather    import OWMForecast
from .pvmodel        import PVModel
from .solcast        import SolCast
from .visualcrossing import VisualCrossing
from .entsoe         import EntsoE
from .co2signal      import CO2signal
from .csvinput       import CSVInput
from .dbrepository   import DBRepository
from .influx         import InfluxRepo

class ForecastManager:
    def __init__(self, configFile):
        try:
            config = configparser.ConfigParser(inline_comment_prefixes='#', empty_lines_in_values=False)
            if not os.path.isfile(configFile): 
                sys.tracebacklimit=0
                raise Exception ('File does not exist')
            config.read(configFile)
        except Exception as e:
            print("Error reading config file '" + configFile + "': " + str(e))
            sys.exit(1)

        self.config     = config

    def _check_hasPVModel(self, what):        
        if not PVModel.__operational__:
            print("Error: Can't run " + what + " - pvlib library installation missing or old version (required: >=0.9.0)")
            sys.exit(1)
        if 'PVSystem' not in self.config.sections():
            print("Warning: Can't run " + what + " without section 'PVSystem' in config file, skipped")
            return False
        return True

    def processDWDFile(self, file = 'L'):
        """processes one MOSMIX file from DWD (https://wettwarn.de/mosmix/mosmix.html):

        file = 'L':           download and process MOSMIX_L file (... for selected station, new file every 6 hours)
        file = 'S':           download and process MOSMIX_S file (... these are large files, 37MByte compressed, hourly)
        file = <file_name>    process <file_name> already on disk
        
        to do: file processing can handle MOSMIX_L and station specific extracts from MOSMIX_S
               (stored in an earlier run with 'storeKMZ = 1' in config file
               It cannot handle raw MOSMIX_S files (stored with 'keepKMZ_S = 1')"""

        if not self._check_hasPVModel('MOSMIX_' + file): 
            return
        #------------------------------------------------------------------------------- Weather data handling
        myWeather = DWDForecast(self.config)
        if (file == 'L'):                                                                # download and process MOSMIX_L
            myWeather.getForecast_DWD_L()
        elif (file == 'S'):                                                              # download and process MOSMIX_S
            myWeather.getForecast_DWD_S()
        else:
            myWeather.readKML(file)
        if myWeather.parseKML():                                                         # successful parsing done ...
            myWeather.convertDT()                                                        # strip-down and rename weather data to what is needed by PVModel

            #--------------------------------------------------------------------------- PV Forecast handling
            myPV  = PVModel(self.config)
            model = self.config['DWD'].get('Irradiance', 'disc')
            myPV.run_splitArray(myWeather, model)
            myWeather.merge_PVSim(myPV)                                                  # merge stripped-down weather data and forecast

            #--------------------------------------------------------------------------- CSV storage
            if (self.config['DWD'].getboolean('storeCSV', False)):                       # store full weather data to .csv
                myWeather.writeCSV()

            #--------------------------------------------------------------------------- SQLite storage
            if (self.config['DWD'].getboolean('storeDB')):
                myDB = DBRepository(self.config)
                myDB.loadData(myWeather)
                del myDB                                                                 # force closure of DB

            #--------------------------------------------------------------------------- Influx storage
            if (self.config['DWD'].getboolean('storeInflux')):
                myInflux = InfluxRepo(self.config)
                myInflux.loadData(myWeather)

    def processDWDDirectory(self, directory, extension):
        """process directory full of MOSMIX files through processDWDFile
        All files with matching 'extension' are processed"""

        cnt = 0
        for entry in os.scandir(directory):
            if entry.path.endswith(extension) and entry.is_file():
                self.processDWDFile(entry.path)
                cnt = cnt+1
        print("Processed " + str(cnt) + " files")

    def processSolCast(self):
        mySolCast = SolCast(self.config)
        mySolCast.getSolCast()

    def processVisualCrossing(self):
        if not self._check_hasPVModel('VisualCrossing'):
            return
        storeDB     = self.config['VisualCrossing'].getboolean('storeDB')
        storeInflux = self.config['VisualCrossing'].getboolean('storeInflux')
        storeCSV    = self.config['VisualCrossing'].getboolean('storeCSV')
        if storeDB or storeInflux or storeCSV:                                           # else there is no storage location ...    
            myWeather  = VisualCrossing(self.config)
            if myWeather.getForecast_VisualCrossing():
                last_issue = datetime.fromtimestamp(0, timezone.utc)
                if storeDB:
                    myDB       = DBRepository(self.config)
                    last_issue = myDB.getLastIssueTime(myWeather.SQLTable)
                if storeInflux: 
                    myInflux   = InfluxRepo(self.config)
                    last_issue = myInflux.getLastIssueTime(myWeather.SQLTable)
                issue_time = datetime.fromisoformat(myWeather.IssueTime)
                delta_t    = round((issue_time - last_issue).total_seconds()/60)         # elapsed time since last download
                force      = self.config['VisualCrossing'].getboolean('force', False)    # force download - for debugging
                if delta_t > 58 or force:                                                # hourly data, allow 2min slack
                    myPV   = PVModel(self.config)

                    model = self.config['VisualCrossing'].get('Irradiance', 'disc')
                    myPV.run_splitArray(myWeather, model)
                    myWeather.merge_PVSim(myPV)
                    if storeDB:     myDB.loadData(myWeather)
                    if storeInflux: myInflux.loadData(myWeather)
                    if storeCSV:    myWeather.writeCSV()
        else:
            print("Warning - getting VisualCrossing data not supported without database storage enabled (storeDB, storeInflux or storeCSV)")
 
    def processOpenWeather(self):
        if not self._check_hasPVModel('OpenWeatherMap'):
            return
        storeDB     = self.config['OpenWeatherMap'].getboolean('storeDB')
        storeInflux = self.config['OpenWeatherMap'].getboolean('storeInflux')
        storeCSV    = self.config['OpenWeatherMap'].getboolean('storeCSV')
        if storeDB or storeInflux or storeCSV:                                           # else there is no storage location ...    
            myWeather = OWMForecast(self.config)
            if myWeather.getForecast_OWM():
                last_issue = datetime.fromtimestamp(0, timezone.utc)
                if storeDB:     
                    myDB       = DBRepository(self.config)
                    last_issue = myDB.getLastIssueTime(myWeather.SQLTable)
                if storeInflux: 
                    myInflux   = InfluxRepo(self.config)
                    last_issue = myInflux.getLastIssueTime(myWeather.SQLTable)
                issue_time = datetime.fromisoformat(myWeather.IssueTime)
                delta_t    = round((issue_time - last_issue).total_seconds()/60)         # elapsed time since last download
                force      = self.config['OpenWeatherMap'].getboolean('force', False)    # force download - for debugging
                if delta_t > 58 or force:                                                # hourly data, allow 2min slack
                    myPV   = PVModel(self.config)

                    model = self.config['OpenWeatherMap'].get('Irradiance', 'clearsky_scaling')
                    myPV.run_splitArray(myWeather, model)
                    myWeather.merge_PVSim(myPV)
                    if storeDB:     myDB.loadData(myWeather)
                    if storeInflux: myInflux.loadData(myWeather)
                    if storeCSV:    myWeather.writeCSV()
        else:
            print("Warning - getting OpenWeatherMap data not supported without database storage enabled (storeDB, storeInflux or storeCSV)")

    def processEntsoE(self, start=None):
        """Process CO2 estimates and forecasts based on Entso-E from transparency.entsoe.eu"""
        if not EntsoE.__operational__:
            print("Error: Can't run Entso-E - entsoe library installation missing")
            sys.exit(1)

        storeDB     = self.config['Entso-E'].getboolean('storeDB')
        storeInflux = self.config['Entso-E'].getboolean('storeInflux')
        storeCSV    = self.config['Entso-E'].getboolean('storeCSV')
        loop        = self.config['Entso-E'].getboolean('loop', False) 
        if loop and start is None:
            if not (storeDB or storeInflux):
                print('Entso-E: looping attempted without database storage (storeInflux, storeDB)')
                sys.exit(1)
            day         = pd.Timestamp(self.config['Entso-E'].get('start'), tz='UTC')
            end         = pd.Timestamp(self.config['Entso-E'].get('end'),   tz='UTC')
            if day is not None and end is not None:
                while day <= end:
                    self.processEntsoE(day)
                    day = day + timedelta(days=1)
            else:
                print('Entso-E: looping attempted without start and end defined')
                sys.exit(1)

        else:
            if loop: storeCSV = False
            if storeDB or storeInflux or storeCSV:                                           # else there is no storage location ...    
                myEntsoE = EntsoE(self.config, start)
                myEntsoE.getData_EntsoE()
                for zone in myEntsoE.zones:                                                  # EntsoE can write multiple tables (one per zone)
                    if myEntsoE.prepareDump(zone):                                           # we have data for this zone
                        last_issue = datetime.fromtimestamp(0, timezone.utc)
                        if storeDB:     
                            myDB       = DBRepository(self.config)
                            last_issue = myDB.getLastIssueTime(myEntsoE.SQLTable)
                        if storeInflux: 
                            myInflux   = InfluxRepo(self.config)
                            last_issue = myInflux.getLastIssueTime(myEntsoE.SQLTable)
                        issue_time = datetime.fromisoformat(myEntsoE.IssueTime)
                        delta_t    = round((issue_time - last_issue).total_seconds()/60)     # elapsed time since last download
                        force      = self.config['Entso-E'].getboolean('force', False)       # force download - for debugging
                        if delta_t > 13 or force or loop:                                    # quarter hourly data, allow 2min slack
                            if storeDB:     myDB.loadData(myEntsoE)
                            if storeInflux: myInflux.loadData(myEntsoE)
                            if storeCSV:    myEntsoE.writeCSV()
            else:
                print("Warning - getting Entso-E data not supported without database storage enabled (storeDB, storeInflux or storeCSV)")

    def processCO2signal(self):
        """Process CO2 estimates and forecasts based on CO2signal from electricityMaps.com"""
        storeDB     = self.config['CO2signal'].getboolean('storeDB')
        storeInflux = self.config['CO2signal'].getboolean('storeInflux')
        if storeDB or storeInflux:                                                       # storeCSV not supported: too trivial
            myCO2signal   = CO2signal(self.config)
            myCO2signal.getData_CO2signal()
            for zone in myCO2signal.zones:                                               # CO2signal can write multiple tables (one per zone)
                myCO2signal.prepareDump(zone)
                if storeDB:     
                    myDB       = DBRepository(self.config)
                if storeInflux: 
                    myInflux   = InfluxRepo(self.config)
                if storeDB:     myDB.loadData(myCO2signal)
                if storeInflux: myInflux.loadData(myCO2signal)
        else:
            print("Warning - getting CO2signal data not supported without database storage enabled (storeDB or storeInflux)")

    def processFileInput(self):
        """Process various input files, for debugging. Based on config file section 'FileInput'"""
        type = self.config['FileInput'].get('type', 'csv')
        file = self.config['FileInput'].get('file')
        if type == 'csv' or type == 'kml':
            if type == 'kml':
                if os.path.isfile(file):
                    self.processDWDFile(file)
                elif os.path.isdir(file):
                    extension = self.config['FileInput'].get('extension', '.zip')
                    if extension[0] != '.': extension = '.' + extension
                    if not os.path.isdir(file):
                        sys.tracebacklimit=0
                        raise Exception("procsessFileInput: Directory '" + file + "' not found")
                    self.processDWDDirectory(file, extension)
                else:
                    sys.tracebacklimit=0
                    raise Exception("processFileInput: '" + file + "' is neither a file nor directory")

            elif type == 'csv':
                if not os.path.isfile(file):
                    sys.tracebacklimit=0
                    raise Exception("processFileInput: File '" + file + "' not found")
                myWeather = CSVInput(self.config)
                myWeather.getForecast_CSVInput(file)
                myPV      = PVModel(self.config)
                model     = self.config['FileInput'].get('Irradiance', 'disc')
                myPV.run_splitArray(myWeather, model)
                myWeather.merge_PVSim(myPV)
                myWeather.writeCSV()                                                     # unconditional writing to CSV, other store paths not supported

            else:
                sys.tracebacklimit=0
                raise Exception("processFileInput: type '" + type + "' unsupported")
        return()

    def runForecasts(self):
        methods = ['MOSMIX_L', 'MOSMIX_S', 'SolCast', 'VisualCrossing', 'OpenWeatherMap', 'Entso-E', 'CO2signal', 'FileInput']
        runList = []
        if 'Forecasts' in self.config.sections():
            for m in methods:
                if self.config['Forecasts'].getboolean(m, False):
                    if m == 'MOSMIX_L' or m == 'MOSMIX_S': _m = 'DWD'
                    else:                                  _m = m
                    if _m not in self.config.sections():
                        print("Warning: config file doesn't contain information for '" + m + "', skipped")
                    else:
                        runList.append(m)
        else:
            for m in self.config.sections():
                if m == 'DWD': _m = 'MOSMIX_L'
                else:          _m = m
                if _m in methods:
                    runList.append(_m)

        if len(runList) == 0:
            print("Error: no data providers selected in config file")
            sys.exit(1)

        if 'MOSMIX_L'       in runList: self.processDWDFile('L')     # gets latest forecast (MOSMIX_L - DWD)
        if 'MOSMIX_S'       in runList: self.processDWDFile('S')     # gets latest forecast (MOSMIX_S - DWD)
        if 'SolCast'        in runList: self.processSolCast()        # get / post solcast
        if 'VisualCrossing' in runList: self.processVisualCrossing() # get VisualCrossing data
        if 'OpenWeatherMap' in runList: self.processOpenWeather()    # get OpenWeatherMap data
        if 'Entso-E'        in runList: self.processEntsoE()         # Entso-E based CO2 forecast
        if 'CO2signal'      in runList: self.processCO2signal()      # CO2signal from electricityMaps.com
        if 'FileInput'      in runList: self.processFileInput()      # process file input
