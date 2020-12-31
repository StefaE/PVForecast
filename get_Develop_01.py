from PVForecast.dwdforecast  import DWDForecast
from PVForecast.openweather  import OWMForecast
from PVForecast.pvmodel      import PVModel
from PVForecast.solcast      import SolCast
from PVForecast.dbrepository import DBRepository
from PVForecast.influx       import InfluxRepo
import configparser
import os
import sys
from datetime import datetime, timezone

def processDWDFile(file = None):
    #----------------------------------------------------------------------------------- Weather data handling
    myWeather = DWDForecast(myConfig)
    if (not file):
        myWeather.getForecast_DWD_L()
    else:
        myWeather.readKML(file)
    myWeather.parseKML()
    if (myConfig['DWD'].getboolean('storeCSV')):                                         # store weather to .csv
        myWeather.writeCSV()

    #----------------------------------------------------------------------------------- PV Forecast handling
    myPV = PVModel(myConfig)
    myPV.init()
    myPV.run_allModels(myWeather)
    if (myConfig['PVSystem'].getboolean('storeCSV')):                                    # store PV simulations to .csv
        myPV.writeCSV(myWeather.kmlName)

    #----------------------------------------------------------------------------------- SQLite storage
    if (myConfig['DWD'].getboolean('storeDB')):
        myDB = DBRepository(myConfig)
        myDB.loadData(myWeather)
        myDB.loadData(myPV)
        del myDB                                                                         # force closure of DB

    if (myConfig['DWD'].getboolean('storeInflux')):
        myInflux = InfluxRepo(myConfig)
        myInflux.loadData(myPV)

def processDWDDirectory(directory, extension):
    cnt = 0
    for entry in os.scandir(directory):
        if entry.path.endswith(extension) and entry.is_file():
            processDWDFile(entry.path)
            cnt = cnt+1
    print("Processed " + str(cnt) + " files")

def processSolCast():
    if (myConfig['SolCast'].getboolean('storeDB')):
        mySolCast = SolCast(myConfig)
        mySolCast.getSolCast()
        if (myConfig['SolCast'].getboolean('storeInflux')):
            myInflux = InfluxRepo(myConfig)
            myInflux.loadData(mySolCast)
    else:
        print("Warning - getting SolCast data not supported without database storage enabled")

def processOpenWeather():
    if (myConfig.getboolean('OpenWeatherMap', 'storeDB')):                               # else, we have no place to put the data ...
        myOpenWeather = OWMForecast(myConfig)
        myOpenWeather.getForecast_OWM()
        myDB = DBRepository(myConfig)
        last_issue    = myDB.getLastIssueTime(myOpenWeather.SQLTable)
        issue_time    = datetime.fromisoformat(myOpenWeather.IssueTime)
        delta_t       = round((issue_time - last_issue).total_seconds()/60)              # elapsed time since last download
        if (delta_t > 58):                                                               # hourly data, allow 2min slack
            myPV      = PVModel(myConfig)
            myPV.init()
            myPV.run_allModels(myOpenWeather)
            myOpenWeather.merge_PVSim(myPV)
            myDB = DBRepository(myConfig)
            myDB.loadData(myOpenWeather)
            if (myConfig['OpenWeatherMap'].getboolean('storeInflux')):
                myInflux = InfluxRepo(myConfig)
                myInflux.loadData(myOpenWeather)
    else:
        print("Warning - getting OpenWeatherMap data not supported without database storage enabled")

def measure_temp():
    temp = os.popen("vcgencmd measure_temp").readline()
    print("CPU Temperature: " + temp) 
    return (temp.replace("temp=", ""))        

if __name__ == "__main__":
    try:
        myConfig = configparser.ConfigParser(inline_comment_prefixes='#')
        myConfig.read('config.ini')
    except Exception as e:
        print("Error reading config file config.ini: " + str(e))
        sys.exit(1)
    
    #processDWDFile()                                                                    # gets latest forecast and processes
    #processDWDFile('./temp/MOSMIX_L_2020110309_K1176.kml.gz')                           # processes one file from disk
    #processDWDDirectory('./download', '.zip')                                           # processes all files in directory (with extension)
    processSolCast()
    #processOpenWeather()
    measure_temp()

    print("------------------------- End ...")