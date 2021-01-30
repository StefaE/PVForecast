import pandas as pd
import time
import pytz
import sys
from datetime  import datetime, timezone, timedelta
from influxdb  import DataFrameClient
from influxdb  import InfluxDBClient

from .forecast import Forecast

class InfluxRepo:
    def __init__(self, config):
        self.config    = config
        self._host     = self.config['Influx'].get('host')
        self._port     = self.config['Influx'].getint('port', 8086)
        self._database = self.config['Influx'].get('database')

    def loadData(self, data: Forecast):
        if (data.InfluxFields):
            client   = DataFrameClient(host=self._host, port=self._port, database=self._database)
            client.write_points(data.DataTable[data.InfluxFields]+0.0, data.SQLTable)  # +0.0 to force float

            issueTime = datetime.fromisoformat(data.IssueTime)
            issueTime = int(time.mktime(issueTime.timetuple()))
            now_utc   = datetime.now(timezone.utc)
            df        = pd.DataFrame(data={'IssueTime': issueTime, 'Table': [data.SQLTable]}, index=[now_utc])
            client.write_points(df, 'forecast_log', tag_columns=['Table'])

    def getLastIssueTime(self, table):
        client = InfluxDBClient(host=self._host, port=self._port, database=self._database)
        measArr  = client.get_list_measurements()
        hasTable = False
        for meas in measArr:
            if meas['name'] == table: hasTable = True
        if hasTable:
            select = client.query("""SELECT Last("IssueTime") AS "IssueTime" FROM "forecast_log" WHERE "Table"='""" + table + """'""")
            for row in select.get_points():
                IssueTime = row['IssueTime']
                IssueTime = datetime.fromtimestamp(IssueTime)
                IssueTime = pytz.timezone('UTC').localize(IssueTime)
        else:
            IssueTime = datetime(1990, 1, 1, 0, 0, 0, 0,timezone.utc)
        return(IssueTime)

    def getPostData(self, solcast):
        try:
            endTime   = datetime.fromisoformat(solcast.IssueTime)
            delta_t   = round((endTime - solcast.last_issue).total_seconds()/60)         # delta_t = time since last IssueTime
            if delta_t > 14400: delta_t = 1440                                           # limit to 1 days (in case of downtime)
            endTime   = endTime - timedelta(minutes=5)                                   # keep last 5min interval for next call ...
            startTime = endTime - timedelta(minutes=delta_t)

            endTime   = endTime.strftime('%Y-%m-%dT%H:%M:%SZ')
            startTime = startTime.strftime('%Y-%m-%dT%H:%M:%SZ')

            meas, field = self.config['Influx'].get('power_field').split('.')

            client    = InfluxDBClient(host=self._host, port=self._port, database=self._database)
            sql         = 'SELECT mean("' + field +'") AS "total_power" FROM "' + meas + '" WHERE time >= ' + "'" + startTime + "' AND time < '" + endTime + "' GROUP BY time(5m)"
            select      = client.query(sql)
            postDict    = []
            hasData     = False
            for row in select.get_points():
                hasData = True                                                           # if we don't get here, most likely 'power_field' was wrongly configured
                if row['total_power'] is not None and row['total_power'] > 0:         
                    period_end = row['time'].replace("Z", "+00:00")                      # Influx returns period_start, so we need add 5min
                    period_end = datetime.fromisoformat(period_end) + timedelta(minutes=5)
                    period_end = period_end.strftime('%Y-%m-%dT%H:%M:%SZ')               # ... and convert back to a string
                    postDict.append( { 'period_end'  : period_end,
                                       'period'      : 'PT5M',
                                       'total_power' : row['total_power']/1000 })
            if not hasData:
                print("Warning --- no generated power data found to post... Wrong 'power_field' definition?")
            if len(postDict) > 0: postDict = { "measurements": postDict }
            else:                 postDict = None
            return(postDict)
        except Exception as e:
            print("getPostData: " + str(e))
            sys.exit(1)