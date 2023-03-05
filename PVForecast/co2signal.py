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
import requests
import json
from datetime import datetime, timezone

from .forecast import Forecast

class CO2signal(Forecast):
    """Class for managing CO2signal data from electricityMaps.com"""
    def __init__(self, config):
        """Initialize CO2signal
        config      configparser object with section [CO2signal]"""

        super().__init__()
        self.config    = config

        zoneLst        = self.config['CO2signal'].get('zones')
        zoneLst        = zoneLst.replace(" ", "")
        self.zones     = zoneLst.split(",")

        self._api_key  = self.config['CO2signal'].get('api_key')
        self._url      = 'https://api.co2signal.com/v1/latest'

        self.SQLTable  = 'co2signal'
        self.IssueTime = str(pd.Timestamp.now(timezone.utc).round('1s'))
        self.storePath = self.config['CO2signal'].get('storePath')

        self._co2      = {}

    def prepareDump(self, zone):
        self.SQLTable     = 'co2signal_' + zone
        self.DataTable    = self._co2[zone]
        self.InfluxFields = self.get_ParaNames()

    def getData_CO2signal(self):
        for zone in self.zones:
            response          = requests.get(self._url, headers={'auth-token': self._api_key}, params={'countryCode': zone})
            data              = json.loads(response.content)['data']
            data['PeriodEnd'] = datetime.fromisoformat(data['datetime'][:-1] + '+00:00')
            data.pop('datetime')
            df                = pd.Series(data).to_frame().T
            self._co2[zone]   = df.set_index('PeriodEnd')
        return