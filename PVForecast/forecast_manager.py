import configparser
import sys
import os
from datetime import datetime, timezone

from .dwdforecast  import DWDForecast
from .openweather  import OWMForecast
from .pvmodel      import PVModel
from .solcast      import SolCast
from .dbrepository import DBRepository
from .influx       import InfluxRepo


class ForecastManager:
    def __init__(self, configFile):
        try:
            config = configparser.ConfigParser(inline_comment_prefixes='#', empty_lines_in_values=False)
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
            if (self.config['DWD'].getboolean('storeCSV')):                              # store weather to .csv
                myWeather.writeCSV()

            #---------------------------------------------------------------------------- PV Forecast handling
            myPV  = PVModel(self.config)
            model = self.config['DWD'].get('Irradiance')
            myPV.run_allModels(myWeather, model)
            if (self.config['PVSystem'].getboolean('storeCSV')):                         # store PV simulations to .csv
                myPV.writeCSV(myWeather.kmlName)

            #---------------------------------------------------------------------------- SQLite storage
            if (self.config['DWD'].getboolean('storeDB')):
                myDB = DBRepository(self.config)
                myDB.loadData(myWeather)
                myDB.loadData(myPV)
                del myDB                                                                 # force closure of DB

            if (self.config['DWD'].getboolean('storeInflux')):
                myInflux = InfluxRepo(self.config)
                myInflux.loadData(myPV)

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
 
    def processOpenWeather(self):
        storeDB     = self.config['OpenWeatherMap'].getboolean('storeDB')
        storeInflux = self.config['OpenWeatherMap'].getboolean('storeInflux')
        if storeDB or storeInflux:                                                       # else there is no storage location ...    
            myOpenWeather = OWMForecast(self.config)
            myOpenWeather.getForecast_OWM()
            if storeDB:     myDB     = DBRepository(self.config)
            if storeInflux: myInflux = InfluxRepo(self.config)
            if storeDB: last_issue   = myDB.getLastIssueTime(myOpenWeather.SQLTable)
            else:       last_issue   = myInflux.getLastIssueTime(myOpenWeather.SQLTable)
            issue_time = datetime.fromisoformat(myOpenWeather.IssueTime)
            delta_t    = round((issue_time - last_issue).total_seconds()/60)             # elapsed time since last download
            if (delta_t > 58):                                                           # hourly data, allow 2min slack
                myPV      = PVModel(self.config)

                model = self.config['OpenWeatherMap'].get('Irradiance')
                myPV.run_allModels(myOpenWeather, model)
                myOpenWeather.merge_PVSim(myPV)
                if storeDB:     myDB.loadData(myOpenWeather)
                if storeInflux: myInflux.loadData(myOpenWeather)
        else:
            print("Warning - getting OpenWeatherMap data not supported without database storage enabled (storeDB or storeInflux")

    def runForecasts(self):
        if self.config['Forecasts'].getboolean('MOSMIX_L'): self.processDWDFile('L')     # gets latest forecast (MOSMIX_L - DWD)
        if self.config['Forecasts'].getboolean('MOSMIX_S'): self.processDWDFile('S')     # gets latest forecast (MOSMIX_S - DWD)
        # self.processDWDFile('./temp/MOSMIX_L_2020110309_K1176.kml.gz')                 # processes one MOSMIX file from disk - for debugging
        # self.processDWDDirectory('./download', '.zip')                                 # processes all files in directory (with extension) - for debugging
        if self.config['Forecasts'].getboolean('Solcast'):  self.processSolCast()        # get / post solcast
        if self.config['Forecasts'].getboolean('OWM'):      self.processOpenWeather()    # get OpenWeatherMap data
