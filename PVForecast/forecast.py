class Forecast:
    """Abstract class of forecast data structures"""

    def __init__(self):
        self.DataTable    = None                                                         # Pandas dataframe with most recent read weather data
        self.IssueTime    = None                                                         # Issue time of weather data forecast (string, iso format, UTC)
        self.SQLTable     = None                                                         # SQL table name to be used for storage (see DBRepository.loadData())
        self.InfluxFields = []                                                           # fields to export to InfluxDB

    def get_ParaNames(self):                                                             # get parameter names of self.DataTable
        return(list(self.DataTable))