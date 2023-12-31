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

import sys
import re
import os

import pandas as pd
import numpy  as np

from .forecast import Forecast

class CSVInput(Forecast):
    """Class for processing weather data from a .csv file"""
    def __init__(self, config):
        """Initialize OWMForecast
        config      configparser object with section [FileInput]"""

        super().__init__()
        self.config    = config
        self.storePath = self.config['FileInput'].get('storePath')

    def getForecast_CSVInput(self, file):
        try:
            self.DataTable = pd.read_csv(file)
            self.DataTable['PeriodEnd'] = pd.to_datetime(self.DataTable['PeriodEnd'])
            self.DataTable.set_index('PeriodEnd', verify_integrity=True, inplace=True)
            self.IssueTime = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S+00:00")
            self.csvName   = re.sub(r'\.csv.*$', '_out.csv.gz', file)
            self.csvName   = os.path.basename(self.csvName)
            return()

        except Exception as e:
            print("Error - getForecast_CSVInput: " + str(e))
            sys.exit(1)