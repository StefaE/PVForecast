import requests
import os
import xml.etree.ElementTree as ET
import elementpath
import gzip
from zipfile import ZipFile
from io      import BytesIO

import pandas as pd
import numpy  as np
import re
import sys

from .forecast import Forecast

class DWDForecast(Forecast):
    """Class for downloading and parsing DWD MOSMIX weather forecasts"""

    def __init__(self, config):
        """Initialize DWDForecast
        config      configparser object with section [DWD]"""

        super().__init__()
        self.config        = config
        self.kmlName       = None                                                        # name of .kml file read with getForecast_DWD_L
        self._kmlNS        = { 'dwd' : 'https://opendata.dwd.de/weather/lib/pointforecast_dwd_extension_V1_0.xsd', 
                               'gx'  : 'http://www.google.com/kml/ext/2.2',
                               'kml' : 'http://www.opengis.net/kml/2.2', 
                               'atom': 'http://www.w3.org/2005/Atom', 
                               'xal' : 'urn:oasis:names:tc:ciq:xsdschema:xAL:2.0' }
        self._kml          = None                                                        # xml with wheather data as ElementTree
        self.SQLTable      = 'dwd'                                                       # which SQL table name is this data stored to (see DBRepository.loadData())

    def getForecast_DWD_L(self):                                                         # get forecast from DWD web page --> self.kml as XML elementtree
        """Get newest MOSMIX_L forecast; store file as .zip"""

        baseurl = self.config['DWD'].get('DWD_URL_L')                                    # station based 'long', six-hourly forecast
        station = self.config['DWD'].get('DWDStation')
        url     = baseurl + station + '/kml/MOSMIX_L_LATEST_' + station + '.kmz'
        try:
            req     = requests.get(url)                                                  # get .kmz file
            if (req.reason != 'OK'):
                raise Exception("ERROR --- Can't download file '" + url + "' --- Reason: " + req.reason)
            zipfile = ZipFile(BytesIO(req.content))                                      # .kmz is zip-compressed, so read content as bytestream into ZipFile
            names   = zipfile.namelist()                                                 # find file names in .kmz file
            if (len(names) != 1):                                                        # we expect exactly one file, else we don't know what to do
                raise Exception ("ERROR --- " + str(len(names)) + " files found inside '" + url + "', should be == 1")
            self.kmlName = names[0]
            kmlfile   = zipfile.open(names[0])
            kml       = kmlfile.read()                                                   # xml source as a string
            self._kml = ET.fromstring(kml)
            kmlfile.close()
            if (self.config['DWD'].getboolean('storeKMZ')):
                path   = self.config['DWD'].get('storePath')
                myName = re.sub(r'\.kml', '.zip', self.kmlName)                          # replace .kmz with .zip as more convenient extension
                myName = path + '/' + myName
                if (not os.path.isfile(myName)):                                         # don't over-write pre-existing file
                    open(myName, 'wb').write(req.content)
            self._last_kmlName = self.kmlName

        except Exception as e:
            print ("getForecast_DWD_L: " + str(e))
            sys.exit(1)

    def readKML(self, file):                                                             # read forecast from .kml file --> self.kml as XML elementtree
        """Read MOSMIX_L file and make XML content available internally (to be parsed with parseKML)
        .xml and .kml files are considered XML (possibly .gz-ipped), 
        .zip and .kmz are considered .zip files containing one .kml"""

        try:
            if (bool(re.search(r'.+\.(zip|kmz)$', file, re.IGNORECASE))):
                zipfile = ZipFile(file)
                names   = zipfile.namelist()
                if (len(names) != 1):
                    raise Exception("ERROR --- " + str(len(names)) + " files found inside '" + file + "', should be == 1")
                kml = zipfile.open(names[0]).read()
                self._kml = ET.fromstring(kml)
            elif (bool(re.search(r'\.(kml|xml)\.gz$', file, re.IGNORECASE))):
                self._kml = ET.parse(gzip.open(file, 'r'))
            elif (bool(re.search(r'\.(kml|xml)$', file, re.IGNORECASE))):
                self._kml = ET.parse(file)
            else:
                raise Exception("ERROR --- unknown file type for weather file " + file)
            file          = re.sub(r'\.(zip|kml\.gz|kmz|xml)$', '.kml', file, re.IGNORECASE)
            self.kmlName = os.path.basename(file)

        except Exception as e:
            print ("readKML: " + str(e))
            sys.exit(1)

    def parseKML(self):                                                                  # parse XML to pandas self.DataTable
        """Parse XML content of a MOSMIX .kml file"""

        try:
            self.IssueTime = elementpath.select(self._kml, '//dwd:IssueTime/text()', self._kmlNS)[0]
            self.IssueTime = re.sub('T', ' ', self.IssueTime)
            self.IssueTime = re.sub('.000Z', '+00:00', self.IssueTime)                   # now we have the same format as pandas will eventually output for time steps
            PeriodEnd      = elementpath.select(self._kml, '//dwd:ForecastTimeSteps/dwd:TimeStep/text()', self._kmlNS)
            ParaNames      = elementpath.select(self._kml, '//dwd:Forecast/@dwd:elementName', self._kmlNS)
            valStrArray    = elementpath.select(self._kml, '//dwd:Forecast/dwd:value', self._kmlNS)
            weatherData    = {}
            if (len(ParaNames) != len(valStrArray)):
                raise Exception("ERROR --- length mismatch in parseKML()")
            for i, param in enumerate(ParaNames):
                valStr = valStrArray[i].text.replace('-', 'nan')
                valArr = valStr.split()
                valArr = np.array(valArr)
                valArr = np.asfarray(valArr, float)
                weatherData.update({ param : valArr })
            self.DataTable            = pd.DataFrame(weatherData, index=pd.DatetimeIndex(PeriodEnd))
            self.DataTable.index.name = 'PeriodEnd'                                      # Time is in UTC
            
        except Exception as e:
            print("parseKLM: " + str(e))
            sys.exit(1)

    def writeCSV(self):                                                                  # write self.DataTable to .csv file
        """Write out weather data as .csv.gz file"""

        path   = self.config['DWD'].get('storePath')
        fName  = re.sub(r'\.kml$', '_weather.csv.gz', self.kmlName)
        self.DataTable.to_csv(path + "/" + fName, compression='gzip')
