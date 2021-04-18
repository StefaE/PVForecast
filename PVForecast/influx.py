import pandas as pd
import time
import pytz
import sys
from datetime  import datetime, timezone, timedelta
hasInflux_V1 = False
hasInflux_V2 = False
try:
    from influxdb  import DataFrameClient
    from influxdb  import InfluxDBClient
    hasInflux_V1 = True
except ImportError:
    pass
try:
    from influxdb_client import InfluxDBClient as InfluxDBClient_V2
    hasInflux_V2 = True
except:
    pass

from .forecast import Forecast

class InfluxRepo:
    def __init__(self, config):
        self.config     = config
        self._host      = self.config['Influx'].get('host', 'localhost')
        self._port      = self.config['Influx'].getint('port', 8086)
        self._database  = self.config['Influx'].get('database', None)
        self._username  = self.config['Influx'].get('username', 'root')
        self._password  = self.config['Influx'].get('password', 'root')
        self._token     = self.config['Influx'].get('token', None)
        self._org       = self.config['Influx'].get('org', None)
        self._influx_V2 = self.config['Influx'].getboolean('influx_v2', False)
        try:
            if self._influx_V2:
                if self._database is None: self._database = self.config['Influx'].get('bucket')
                if not self._host.startswith('http://'): self._host = 'http://' + self._host
            if self._database is None:
                raise Exception("Influx: No database (bucket) defined")
            if self._influx_V2 and not hasInflux_V2:
                raise Exception("influxdb_client needs be installed for Influx 2.0 support")
            elif not self._influx_V2 and not hasInflux_V1:
                raise Exception("influxdb needs be installed for Influx 1.x support")
        except Exception as e:
            print("InfluxRepo: " + str(e))
            sys.exit(1)

    def loadData(self, data: Forecast):
        if (data.InfluxFields):
            df       = data.DataTable[data.InfluxFields].copy()
            for field in data.InfluxFields:
                df.loc[:,field] = df[field].astype(float)

            issueTime = datetime.fromisoformat(data.IssueTime)
            issueTime = int(time.mktime(issueTime.timetuple()))
            now_utc   = datetime.now(timezone.utc)
            df_log    = pd.DataFrame(data={'IssueTime': issueTime, 'Table': [data.SQLTable]}, index=[now_utc])

            if not self._influx_V2:
                client   = DataFrameClient(host=self._host, port=self._port, database=self._database, username=self._username, password=self._password)
                client.write_points(df, data.SQLTable)
                client.write_points(df_log, 'forecast_log', tag_columns=['Table'])
            else:
                client    = InfluxDBClient_V2(url=self._host+":"+str(self._port), token=self._token, org=self._org)
                write_api = client.write_api()
                write_api.write(self._database, record=df,     data_frame_measurement_name=data.SQLTable)
                write_api.write(self._database, record=df_log, data_frame_measurement_name='forecast_log', data_frame_tag_columns=['Table'])
                write_api.close()
                client.close()
 
    def getLastIssueTime(self, table):
        IssueTime = None
        if not self._influx_V2:
            client = InfluxDBClient(host=self._host, port=self._port, database=self._database, username=self._username, password=self._password)
            select = client.query("""SELECT Last("IssueTime") AS "IssueTime" FROM "forecast_log" WHERE "Table"='""" + table + """'""")
            for row in select.get_points():
                IssueTime = row['IssueTime']
        else:
            client    = InfluxDBClient_V2(url=self._host+":"+str(self._port), token=self._token, org=self._org)
            query_api = client.query_api()
            rows      = query_api.query_stream('from(bucket:"' + self._database + '") '
                                               '  |> range(start: -3h) '
                                               '  |> filter(fn: (r) => r._measurement == "forecast_log") '
                                               '  |> filter(fn: (r) => r._field       == "IssueTime") '
                                               '  |> filter(fn: (r) => r.Table        == "' + table + '") '
                                               '  |> last()')
            for row in rows:
                IssueTime = row['_value']
            client.close()

        if IssueTime is not None:
            IssueTime = datetime.fromtimestamp(IssueTime)
            IssueTime = pytz.timezone('UTC').localize(IssueTime)
        else:
            IssueTime = datetime(1990, 1, 1, 0, 0, 0, 0,timezone.utc)
        return(IssueTime)

    def getPostData(self, solcast, power_field):
        try:
            if self._influx_V2:
                raise Exception("Solcast post not supported for Influx V2 databases")
            endTime   = datetime.fromisoformat(solcast.IssueTime)
            delta_t   = round((endTime - solcast.last_issue).total_seconds()/60)         # delta_t = time since last IssueTime
            if delta_t > 14400: delta_t = 1440                                           # limit to 1 days (in case of downtime)
            endTime   = endTime - timedelta(minutes=5)                                   # keep last 5min interval for next call ...
            startTime = endTime - timedelta(minutes=delta_t)

            endTime   = endTime.strftime('%Y-%m-%dT%H:%M:%SZ')
            startTime = startTime.strftime('%Y-%m-%dT%H:%M:%SZ')

            meas, field = self.config['Influx'].get(power_field).split('.')

            client      = InfluxDBClient(host=self._host, port=self._port, database=self._database, username=self._username, password=self._password)           # <===================================
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
                                       'total_power' : row['total_power']/1000 } )
            if not hasData:
                print("Warning --- no generated power data found to post... Wrong 'power_field' definition?")
            if len(postDict) > 0: postDict = { "measurements": postDict }
            else:                 postDict = None
            return(postDict)
        except Exception as e:
            print("getPostData: " + str(e))
            sys.exit(1)