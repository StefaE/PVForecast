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
import sys

import pandas as pd

from .forecast import Forecast

class VisualCrossing(Forecast):
    """Class for downloading weather data from visualcrossing.com"""
    def __init__(self, config):
        """Initialize VisualCrossing
        config      configparser object with section [VisualCrossing]"""

        super().__init__()
        self.config    = config
        self.SQLTable  = 'visualcrossing'
        self.storePath = self.config['VisualCrossing'].get('storePath')

    def getForecast_VisualCrossing(self):
        try:
            latitude  = str(self.config['VisualCrossing'].getfloat('Latitude'))
            longitude = str(self.config['VisualCrossing'].getfloat('Longitude'))
            apikey    = self.config['VisualCrossing'].get('api_key')
            url       = 'https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/' + latitude + '%2C' + longitude + '?unitGroup=metric&include=hours&key=' + apikey + '&contentType=json'
            req       = requests.get(url)
            if (req.status_code != 200):                                                   # ... for some reason, req.reason is empty
                sys.tracebacklimit=0
                raise Exception("ERROR --- Can't fetch VisualCrossing data from '" + url + "' --- Reason: " + req.reason)
            value          = req.json()
            dict           = {}
            self.IssueTime = None
            dropWeather    = self.config['VisualCrossing'].getboolean('dropWeather', True)
            for day in value['days']:
                for hour in day['hours']:
                    if hour['source'] == 'fcst':                                           # we only evaluate forecast values but API also returns 'obs' values for past hours of current day
                        if self.IssueTime is None: 
                            self.IssueTime = hour['datetimeEpoch'] - 1800
                        dict[hour['datetimeEpoch'] + 1800] = {                             # VisualCrossing reports GHI at moment of reporting index. Hence, we set PeriodEnd to 30min later
                            'temp_air'   : hour['temp'] + 273.15,                          # ... so, GHI value should mimic average between 30min prior and 30min past the time stamp
                            'temp_dew'   : hour['dew']  + 273.15,                          # convert to Kelvin
                            'wind_speed' : hour['windspeed'],
                            'pressure'   : hour['pressure']*100,                           # covert milli-bar to pascal
                            'clouds'     : hour['cloudcover'],
                            'ghi'        : hour['solarradiation']
                        }
                        if not dropWeather:
                            for elem in hour:
                                if (elem not in ['temp', 'dew', 'windspeed', 'pressure', 'cloudcover', 'solarradiation', 'source', 'datetime', 'datetimeEpoch']) \
                                   and (isinstance(hour[elem], int) or isinstance(hour[elem], float)):
                                    dict[hour['datetimeEpoch'] + 1800][elem] = hour[elem]

            self.DataTable            = pd.DataFrame.from_dict(dict, orient='index')                
            idx                       = pd.to_datetime(self.DataTable.index, unit='s', utc=True)
            self.DataTable.set_index(idx, inplace=True)
            self.DataTable.index.name = 'PeriodEnd'
            self.IssueTime            = str(pd.to_datetime(self.IssueTime, unit='s', utc=True))
            self.csvName      = 'visualcrossing_' + self.IssueTime[:16].replace(' ', '_').replace(':', '-') + '.csv.gz'
            return(True)
            
        except Exception as e:
            print("getForecast_VisualCrossing: " + str(e))
            return(False)

