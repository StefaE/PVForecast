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

from datetime import datetime, timezone
import requests
import sys

import pandas as pd
from pandas.api.types import is_numeric_dtype

from .forecast import Forecast

class OWMForecast(Forecast):
    """Class for downloading weather data from openweathermap.org"""
    def __init__(self, config):
        """Initialize OWMForecast
        config      configparser object with section [OpenWeatherMap]"""

        super().__init__()
        self.config    = config
        self.SQLTable  = 'owm'
        self.storePath = self.config['OpenWeatherMap'].get('storePath')

    def getForecast_OWM(self):
        try:
            latitude  = str(self.config['OpenWeatherMap'].getfloat('Latitude'))
            longitude = str(self.config['OpenWeatherMap'].getfloat('Longitude'))
            apikey    = self.config['OpenWeatherMap'].get('api_key')
            url = 'https://api.openweathermap.org/data/2.5/onecall?lat=' + latitude + '&lon=' + longitude + '&exclude=minutely,daily,alerts&appid=' + apikey
            req = requests.get(url)
            if (req.reason != 'OK'):
                sys.tracebacklimit=0
                raise Exception("getForecast_OWM: Can't fetch OpenWeatherMap data from '" + url + "' --- Reason: " + req.reason)
            self.DataTable     = pd.DataFrame(req.json()['hourly'])
            df_idx             = pd.to_datetime(self.DataTable['dt'], unit='s', utc=True)
            self.DataTable.set_index(df_idx, inplace=True)
            self.DataTable.index.name = 'PeriodEnd'
            drop               = ['dt']
            dropWeather        = self.config['OpenWeatherMap'].getboolean('dropWeather', True)
            for field in list(self.DataTable):
                if (field not in ['temp', 'wind_speed', 'pressure', 'dew_point', 'clouds']) and \
                    (dropWeather or not is_numeric_dtype(self.DataTable[field])): 
                        drop.append(field)
            self.DataTable.drop(drop, axis=1, inplace=True)                              # drop columns which are either not useful or non-float
            self.DataTable.rename(columns = {'temp': 'temp_air', 'dew_point': 'temp_dew'}, inplace=True)
            self.IssueTime     = str(datetime.fromtimestamp(req.json()['current']['dt'], timezone.utc))
            self.csvName       = 'owm_' + self.IssueTime[:16].replace(' ', '_').replace(':', '-') + '.csv.gz'
            return(True)

        except Exception as e:
            print("getForecast_OWM: " + str(e))
            return(False)
