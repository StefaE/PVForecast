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

This is the main script to run a simulation of PVControl for one or multiple days. 
This script is typically called interactively on a performant machine. By default, 
config.ini in the local directory is the configuration file. But argument -c can
specify a different file.
"""

import configparser
import sys
import os
from datetime import datetime, timezone

from .dwdforecast    import DWDForecast
from .openweather    import OWMForecast
from .pvmodel        import PVModel
from .solcast        import SolCast
from .visualcrossing import VisualCrossing
from .csvinput       import CSVInput
from .dbrepository   import DBRepository
from .influx         import InfluxRepo


class ForecastManager:
    def __init__(self, configFile):
        try:
            config = configparser.ConfigParser(inline_comment_prefixes='#', empty_lines_in_values=False)
            if not os.path.isfile(configFile): raise Exception ('File does not exist')
            config.read(configFile)
        except Exception as e:
            print("Error reading config file '" + configFile + "': " + str(e))
            sys.exit(1)

        self.config = config

    def processDWDFile(self, file = 'L'):
        """processes one MOSMIX file from DWD (https://wettwarn.de/mosmix/mosmix.html):

        file = 'L':           download and process MOSMIX_L file (... for selected station, new file every 6 hours)
        file = 'S':           download and process MOSMIX_S file (... these are large files, 37MByte compressed, hourly)
        file = <file_name>    process <file_name> already on disk
        
        to do: file processing can handle MOSMIX_L and station specific extracts from MOSMIX_S
               (stored in an earlier run with 'storeKMZ = 1' in config file
               It cannot handle raw MOSMIX_S files (stored with 'keepKMZ_S = 1')"""

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
            if (self.config['DWD'].getboolean('storeCSV', 0)):                           # store full weather data to .csv
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
        storeDB     = self.config['VisualCrossing'].getboolean('storeDB')
        storeInflux = self.config['VisualCrossing'].getboolean('storeInflux')
        storeCSV    = self.config['VisualCrossing'].getboolean('storeCSV')
        if storeDB or storeInflux or storeCSV:                                           # else there is no storage location ...    
            myWeather  = VisualCrossing(self.config)
            myWeather.getForecast_VisualCrossing()
            last_issue = datetime.fromtimestamp(0, timezone.utc)
            if storeDB:     
                myDB       = DBRepository(self.config)
                last_issue = myDB.getLastIssueTime(myWeather.SQLTable)
            if storeInflux: 
                myInflux   = InfluxRepo(self.config)
                last_issue = myInflux.getLastIssueTime(myWeather.SQLTable)
            issue_time = datetime.fromisoformat(myWeather.IssueTime)
            delta_t    = round((issue_time - last_issue).total_seconds()/60)             # elapsed time since last download
            force      = self.config['VisualCrossing'].getboolean('force', False)        # force download - for debugging
            if delta_t > 58 or force:                                                    # hourly data, allow 2min slack
                myPV   = PVModel(self.config)

                model = self.config['VisualCrossing'].get('Irradiance', 'disc')
                myPV.run_splitArray(myWeather, model)
                myWeather.merge_PVSim(myPV)
                if storeDB:     myDB.loadData(myWeather)
                if storeInflux: myInflux.loadData(myWeather)
                if storeCSV:    myWeather.writeCSV()
        else:
            print("Warning - getting OpenWeatherMap data not supported without database storage enabled (storeDB or storeInflux")
 
    def processOpenWeather(self):
        storeDB     = self.config['OpenWeatherMap'].getboolean('storeDB')
        storeInflux = self.config['OpenWeatherMap'].getboolean('storeInflux')
        storeCSV    = self.config['OpenWeatherMap'].getboolean('storeCSV')
        if storeDB or storeInflux or storeCSV:                                           # else there is no storage location ...    
            myWeather = OWMForecast(self.config)
            myWeather.getForecast_OWM()
            last_issue = datetime.fromtimestamp(0, timezone.utc)
            if storeDB:     
                myDB       = DBRepository(self.config)
                last_issue = myDB.getLastIssueTime(myWeather.SQLTable)
            if storeInflux: 
                myInflux   = InfluxRepo(self.config)
                last_issue = myInflux.getLastIssueTime(myWeather.SQLTable)
            issue_time = datetime.fromisoformat(myWeather.IssueTime)
            delta_t    = round((issue_time - last_issue).total_seconds()/60)             # elapsed time since last download
            force      = self.config['OpenWeatherMap'].getboolean('force', False)        # force download - for debugging
            if delta_t > 58 or force:                                                    # hourly data, allow 2min slack
                myPV   = PVModel(self.config)

                model = self.config['OpenWeatherMap'].get('Irradiance', 'clearsky_scaling')
                myPV.run_splitArray(myWeather, model)
                myWeather.merge_PVSim(myPV)
                if storeDB:     myDB.loadData(myWeather)
                if storeInflux: myInflux.loadData(myWeather)
                if storeCSV:    myWeather.writeCSV()
        else:
            print("Warning - getting OpenWeatherMap data not supported without database storage enabled (storeDB or storeInflux")

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
                        raise Exception("procsessFileInput: Directory '" + file + "' not found")
                    self.processDWDDirectory(file, extension)
                else:
                    raise Exception("processFileInput: '" + file + "' is neither a file nor directory")

            elif type == 'csv':
                if not os.path.isfile(file):
                    raise Exception("processFileInput: File '" + file + "' not found")
                myWeather = CSVInput(self.config)
                myWeather.getForecast_CSVInput(file)
                myPV      = PVModel(self.config)
                model     = self.config['FileInput'].get('Irradiance', 'disc')
                myPV.run_splitArray(myWeather, model)
                myWeather.merge_PVSim(myPV)
                myWeather.writeCSV()                                                     # unconditional writing to CSV, other store paths not supported

            else:
                raise Exception("processFileInput: type '" + type + "' unsupported")

        return()

    def runForecasts(self):
        if self.config['Forecasts'].getboolean('MOSMIX_L'):       self.processDWDFile('L')     # gets latest forecast (MOSMIX_L - DWD)
        if self.config['Forecasts'].getboolean('MOSMIX_S'):       self.processDWDFile('S')     # gets latest forecast (MOSMIX_S - DWD)
        if self.config['Forecasts'].getboolean('Solcast'):        self.processSolCast()        # get / post solcast
        if self.config['Forecasts'].getboolean('VisualCrossing'): self.processVisualCrossing() # get VisualCrossing data
        if self.config['Forecasts'].getboolean('OWM'):            self.processOpenWeather()    # get OpenWeatherMap data
        if self.config['Forecasts'].getboolean('FileInput'):      self.processFileInput()      # process file input
