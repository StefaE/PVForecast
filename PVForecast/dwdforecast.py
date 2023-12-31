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

import requests
import os
import xml.etree.ElementTree as ET
import elementpath
import gzip
from zipfile import ZipFile
from io      import BytesIO
from bs4     import BeautifulSoup

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
        self._kmlNS        = { 'dwd' : 'https://opendata.dwd.de/weather/lib/pointforecast_dwd_extension_V1_0.xsd', 
                               'gx'  : 'http://www.google.com/kml/ext/2.2',
                               'kml' : 'http://www.opengis.net/kml/2.2', 
                               'atom': 'http://www.w3.org/2005/Atom', 
                               'xal' : 'urn:oasis:names:tc:ciq:xsdschema:xAL:2.0' }
        self._kml          = None                                                        # xml with wheather data as ElementTree
        self.kmlName       = None                                                        # used for .csv file name determination
        self.SQLTable      = 'dwd'                                                       # which SQL table name is this data stored to (see DBRepository.loadData())
        self.storePath     = self.config['DWD'].get('storePath')


    def getForecast_DWD_L(self):                                                         # get forecast from DWD web page --> self.kml as XML elementtree
        """Get newest MOSMIX_L forecast (file for selected station); store file as .zip"""

        baseurl = self.config['DWD'].get('DWD_URL_L', 'https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/')        # station based 'long', six-hourly forecast
        station = self.config['DWD'].get('DWDStation')
        url     = baseurl + station + '/kml/MOSMIX_L_LATEST_' + station + '.kmz'
        try:
            req     = requests.get(url)                                                  # get .kmz file
            if (req.reason != 'OK'):
                sys.tracebacklimit=0
                raise Exception("ERROR --- Can't download file '" + url + "' --- Reason: " + req.reason)
            zipfile = ZipFile(BytesIO(req.content))                                      # .kmz is zip-compressed, so read content as bytestream into ZipFile
            names   = zipfile.namelist()                                                 # find file names in .kmz file
            if (len(names) != 1):                                                        # we expect exactly one file, else we don't know what to do
                sys.tracebacklimit=0
                raise Exception ("ERROR --- " + str(len(names)) + " files found inside '" + url + "', should be == 1")
            self.kmlName = names[0]
            kmlfile      = zipfile.open(names[0])
            kml          = kmlfile.read()                                                # xml source as a string
            self._kml    = ET.fromstring(kml)
            kmlfile.close()
            if (self.config['DWD'].getboolean('storeKMZ', False)):
                gzfile   = gzip.open(self.storePath + '/' + self.kmlName + '.gz', 'wb')
                gzfile.write(kml)
                gzfile.close()
            self.csvName = re.sub(r'\.kml$', '.csv.gz', self.kmlName)

        except Exception as e:
            print ("Warning - getForecast_DWD_L: " + str(e))

    def getForecast_DWD_S(self):
        """Get newest MOSMIX_S forecast (global file), extract data for selected station; 
        store extracted file as xxx_<station>.kml.gz"""
        
        url     = self.config['DWD'].get('DWD_URL_S', 'https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_S/all_stations/kml/')
        station = self.config['DWD'].get('DWDStation')
        try:
            req      = requests.get(url)
            if (req.reason != 'OK'):
                sys.tracebacklimit=0
                raise Exception("ERROR --- Can't open page '" + url + "' --- Reason: " + req.reason)
            page     = requests.get(url).text
            soup     = BeautifulSoup(page, 'html.parser')
            files    = [url + '/' + node.get('href') for node in soup.find_all('a') if node.get('href').endswith('kmz')]
            if (len(files) < 2):
                sys.tracebacklimit=0
                raise Exception("ERROR --- Expected to find at least two file links at '" + url + "'")
            myRemote = files[len(files)-2]                                               # file to fetch from remote (last but one, as last is '_LATEST')
            myLocal  = self.storePath + os.path.basename(myRemote)                       # where to store downloaded file
            if (os.path.isfile(myLocal)):
                print('Message - File ' + myLocal + ' already exists, not re-downloaded')
            else:
                if not self.config['DWD'].getboolean('keepKMZ_S', False):                # delete local MOSMIX_S_* files
                    for f in os.listdir(self.storePath):
                        if re.search(r'^MOSMIX_S_', f):
                            f_path = self.storePath + os.path.basename(f)
                            if os.path.isfile(f_path):
                                os.remove(f_path)
                kmlName = os.path.basename(myLocal)
                kmlName = re.sub(r'\.kmz', '.kml', kmlName)
                req     = requests.get(myRemote)
                if (req.reason != 'OK'):
                    sys.tracebacklimit=0
                    raise Exception("ERROR --- Can't download file '" + myRemote + "' --- Reason: " + req.reason)
                open(myLocal, 'wb').write(req.content)

                extract = 1
                kml     = ''
                zipfile = ZipFile(myLocal)
                kmlfile = zipfile.open(kmlName, 'r')
                for line in kmlfile:
                    if (extract == 1):
                        kml += line.decode('UTF-8')
                        if (line.find(rb'</kml:ExtendedData>') > 0):
                            extract = 0
                    elif(extract == 2):
                        kml += line.decode('UTF-8')
                        if (line.find(rb'</kml:Placemark>') > 0):
                            extract = 3
                            break
                    else:
                        if (line.find(('<kml:name>' + station + '</kml:name>').encode()) > 0):
                            kml += '        <kml:Placemark>'
                            kml += line.decode('UTF-8')
                            extract = 2
                kml += '   </kml:Document>\n</kml:kml>'
                kmlfile.close()
                if (extract != 3):
                    sys.tracebacklimit=0
                    raise Exception("ERROR --- Station " + station + " not found")
                self._kml     = ET.fromstring(kml)
                self.SQLTable = 'dwd_s'

                kmlName = re.sub(r'\.kml', '_' + station + '.kml', kmlName)
                self.csvName = re.sub(r'\.kml$', '.csv.gz', kmlName)
                if (self.config['DWD'].getboolean('storeKMZ', False)):
                    self.kmlName = kmlName
                    kmlName = self.storePath + '/' + kmlName + '.gz'
                    if (not os.path.isfile(kmlName)):                                    # don't over-write pre-existing file
                        gzfile = gzip.open(kmlName, 'wt')
                        gzfile.write(kml)
                        gzfile.close()

        except Exception as e:
            print ("Warning - getForecast_DWD_S: " + str(e))


    def readKML(self, file):                                                             # read forecast from .kml file --> self.kml as XML elementtree
        """Read MOSMIX_L file and make XML content available internally (to be parsed with parseKML)
        .xml and .kml files are considered XML (possibly .gz-ipped), 
        .zip and .kmz are considered .zip files containing one .kml"""

        try:
            if (bool(re.search(r'.+\.(zip|kmz)$', file, re.IGNORECASE))):
                zipfile = ZipFile(file)
                names   = zipfile.namelist()
                if (len(names) != 1):
                    sys.tracebacklimit=0
                    raise Exception("ERROR --- " + str(len(names)) + " files found inside '" + file + "', should be == 1")
                kml = zipfile.open(names[0]).read()
                self._kml = ET.fromstring(kml)
            elif (bool(re.search(r'\.(kml|xml)\.gz$', file, re.IGNORECASE))):
                self._kml = ET.parse(gzip.open(file, 'r'))
            elif (bool(re.search(r'\.(kml|xml)$', file, re.IGNORECASE))):
                self._kml = ET.parse(file)
            else:
                sys.tracebacklimit=0
                raise Exception("ERROR --- unknown file type for weather file " + file)
            self.kmlName  = re.sub(r'\.(zip|kml\.gz|kmz|xml)$', '.kml', file, re.IGNORECASE)
            self.kmlName = os.path.basename(self.kmlName)
            self.csvName = re.sub(r'\.kml$', '.csv.gz', self.kmlName)

        except Exception as e:
            print ("readKML: " + str(e))

    def parseKML(self):                                                                  # parse XML to pandas self.DataTable
        """Parse XML content of a MOSMIX .kml file"""

        success = False
        if self._kml is not None:
            try:
                self.IssueTime = elementpath.select(self._kml, '//dwd:IssueTime/text()', self._kmlNS)[0]
                self.IssueTime = re.sub('T', ' ', self.IssueTime)
                self.IssueTime = re.sub('.000Z', '+00:00', self.IssueTime)               # now we have the same format as pandas will eventually output for time steps
                PeriodEnd      = elementpath.select(self._kml, '//dwd:ForecastTimeSteps/dwd:TimeStep/text()', self._kmlNS)
                ParaNames      = elementpath.select(self._kml, '//dwd:Forecast/@dwd:elementName', self._kmlNS)
                valStrArray    = elementpath.select(self._kml, '//dwd:Forecast/dwd:value', self._kmlNS)
                weatherData    = {}
                if (len(ParaNames) != len(valStrArray)):
                    sys.tracebacklimit=0
                    raise Exception("ERROR --- length mismatch in parseKML()")
                for i, param in enumerate(ParaNames):
                    valStr = valStrArray[i].text.replace('-', 'nan')
                    valArr = valStr.split()
                    valArr = np.array(valArr)
                    valArr = np.asfarray(valArr, float)
                    weatherData.update({ param : valArr })
                self.DataTable            = pd.DataFrame(weatherData, index=pd.DatetimeIndex(PeriodEnd))
                self.DataTable.index.name = 'PeriodEnd'                                  # Time is in UTC
                success = True
            
            except Exception as e:
                print("parseKLM: " + str(e))
                success = False

        return(success)

    def convertDT(self):
        dropWeather = self.config['DWD'].getboolean('dropWeather', True)
        if dropWeather:
            drop    = []
            for field in list(self.DataTable):
                if field not in ['TTT', 'Td', 'PPPP', 'FF', 'Neff', 'Rad1h', 'RRad1']: 
                    drop.append(field)
            self.DataTable.drop(drop, axis=1, inplace=True)                              # drop columns which are either not useful or non-float
        self.DataTable.rename(columns = {'TTT'  : 'temp_air', 
                                         'Td'   : 'temp_dew',
                                         'PPPP' : 'pressure',
                                         'FF'   : 'wind_speed',
                                         'Neff' : 'clouds'}, inplace=True)
        if 'Rad1h' in self.DataTable:
            self.DataTable.rename(columns = {'Rad1h': 'ghi'}, inplace=True)
            self.DataTable['ghi'] = self.DataTable['ghi'] * 0.2777778                    # convert to Rad1h [kJ/m^2] to Wh/m^2
        if 'RRad1' in self.DataTable:
            self.DataTable.rename(columns = {'RRad1': 'kt'}, inplace=True)
            self.DataTable['kt'] = self.DataTable['kt']/100                              # convert to RRad1 to kt (/100)
        return()