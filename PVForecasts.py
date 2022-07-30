import os
import argparse
from datetime import datetime
from PVForecast.forecast_manager import ForecastManager

def measure_temp(name):
    """ ... to measure temperature of raspi, as processing can be heavy"""
    temp = os.popen("vcgencmd measure_temp").readline()
    print("CPU Temperature (" + name +"): " + temp) 
    return (temp.replace("temp=", ""))        

if __name__ == "__main__":
    cfgParser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cfgParser.add_argument('-c', '--cfg', help="Specify config file (default: ./config.ini)", metavar="FILE")
    args = cfgParser.parse_args()
    if args.cfg: cfgFile = args.cfg
    else:        cfgFile = 'config.ini'
    print("------------------------- Start (" + cfgFile + ")")
    myForecastManager = ForecastManager(cfgFile)
    myForecastManager.runForecasts()
    print("------------------------- End: " + datetime.now().strftime("%Y-%m-%d, %H:%M:%S"))