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

class Forecast:
    """Abstract class of forecast data structures"""

    def __init__(self):
        self.DataTable    = None                                                         # Pandas dataframe with most recent read weather data
        self.IssueTime    = None                                                         # Issue time of weather data forecast (string, iso format, UTC)
        self.SQLTable     = None                                                         # SQL table name to be used for storage (see DBRepository.loadData())
        self.InfluxFields = []                                                           # fields to export to InfluxDB
        self.csvName      = None
        self.storePath    = None

    def get_ParaNames(self):                                                             # get parameter names of self.DataTable
        return(list(self.DataTable))

    def writeCSV(self):                                                                  # write self.DataTable to .csv file
        if self.csvName is not None and self.storePath is not None:
            try:
                self.DataTable.to_csv(self.storePath + "/" + self.csvName, compression='gzip')

            except Exception as e:
                print("writeCSV: " + str(e))
        else:
            print("writeCSV: csvName or storePath not defined, file not written")

    def merge_PVSim(self, PV):
        self.DataTable    = pd.concat([self.DataTable, PV.DataTable], axis=1)
        self.InfluxFields = PV.InfluxFields
