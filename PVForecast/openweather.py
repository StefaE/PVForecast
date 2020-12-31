from datetime import datetime, timezone
import requests
import sys

import pandas as pd
import numpy  as np

from .forecast import Forecast

class OWMForecast(Forecast):
    def __init__(self, config):
        self.config   = config
        self.SQLTable = 'owm'

    def getForecast_OWM(self):
        try:
            latitude  = str(self.config['OpenWeatherMap'].getfloat('Latitude'))
            longitude = str(self.config['OpenWeatherMap'].getfloat('Longitude'))
            apikey    = self.config['OpenWeatherMap'].get('api_key')
            url = 'https://api.openweathermap.org/data/2.5/onecall?lat=' + latitude + '&lon=' + longitude + '&exclude=minutely,daily,alerts&appid=' + apikey
            req = requests.get(url)
            if (req.reason != 'OK'):
                raise Exception("ERROR --- Can't fetch OpenWeatherMap data from '" + url + "' --- Reason: " + req.reason)
            df                = pd.DataFrame(req.json()['hourly'])
            df_idx            = pd.to_datetime(df['dt'], unit='s', utc=True)
            df                = df.set_index(df_idx)
            df.index.name     = 'PeriodEnd'
            if ('rain' in df):
                drop          = ['dt', 'weather', 'rain']
            else:
                drop          = ['dt', 'weathers']
            self.DataTable    = df.drop(drop, axis=1)
            self.IssueTime    = str(datetime.fromtimestamp(req.json()['current']['dt'], timezone.utc))

        except Exception as e:
            print("OWMForecast: " + str(e))
            sys.exit(1)

    def merge_PVSim(self, PV: Forecast):
        self.DataTable    = pd.concat([self.DataTable, PV.DataTable], axis=1)
        self.InfluxFields = PV.InfluxFields