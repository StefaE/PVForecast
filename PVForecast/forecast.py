import sys

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
                sys.exit(1)
        else:
            print("writeCSV: csvName or storePath not defined")