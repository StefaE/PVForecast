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
import sys
from datetime  import datetime, timezone, timedelta
_hasInflux_V1 = False
_hasInflux_V2 = False
try:
    from influxdb  import DataFrameClient
    from influxdb  import InfluxDBClient
    _hasInflux_V1 = True
except ImportError:
    pass
try:
    from influxdb_client import InfluxDBClient as InfluxDBClient_V2
    _hasInflux_V2 = True
except:
    pass

from .forecast import Forecast

class InfluxRepo:
    """
    Class manages storage (and retrieval) of Forecast objects into Influx 1.x or 2.x
    """
    def __init__(self, config):
        self.config     = config
        if 'Influx' not in self.config.sections():
            sys.tracebacklimit=0
            raise Exception("missing section 'Influx' in config file")
        self._host         = self.config['Influx'].get('host', 'localhost')
        self._posthost     = self.config['Influx'].get('post_host', self._host)
        self._port         = self.config['Influx'].getint('port', 8086)
        self._database     = self.config['Influx'].get('database', None)
        self._postdatabase = self.config['Influx'].get('post_database', self._database)
        self._retention    = self.config['Influx'].get('retention', None)                # retention policy (only for Influx v1.x)
        self._username     = self.config['Influx'].get('username', 'root')
        self._password     = self.config['Influx'].get('password', 'root')
        self._token        = self.config['Influx'].get('token', None)
        self._org          = self.config['Influx'].get('org', None)
        self._influx_V2    = self.config['Influx'].getboolean('influx_v2', False)
        try:
            if self._influx_V2:
                if self._database is None: self._database = self.config['Influx'].get('bucket')
                if not self._host.startswith('http://'): self._host = 'http://' + self._host
            if self._database is None:
                sys.tracebacklimit=0
                raise Exception("Influx: No database (bucket) defined")
            if self._influx_V2 and not _hasInflux_V2:
                sys.tracebacklimit=0
                raise Exception("influxdb_client needs be installed for Influx 2.0 support")
            elif not self._influx_V2 and not _hasInflux_V1:
                sys.tracebacklimit=0
                raise Exception("neither module influxdb nor influxdb_client installed for Influx support")
        except Exception as e:
            print("InfluxRepo: " + str(e))
            sys.exit(1)
        return

    def loadData(self, data: Forecast):
        """
        Load data into Influx. A log of data loaded is maintained in measurement 'forecast_log'

        data    Forecast object to be loaded.
        """
        if (data.InfluxFields):
            df       = data.DataTable[data.InfluxFields].copy()
            for field in data.InfluxFields:
                df[field] = df[field].astype(float)

            issueTime = int(datetime.fromisoformat(data.IssueTime).timestamp())
            now_utc   = datetime.now(timezone.utc)
            df_log    = pd.DataFrame(data={'IssueTime': issueTime, 'Table': [data.SQLTable]}, index=[now_utc])

            if not self._influx_V2:
                client    = DataFrameClient(host=self._host, port=self._port, database=self._database, username=self._username, password=self._password)
                self._verifyDB(client)
                client.write_points(df, data.SQLTable)
                client.write_points(df_log, 'forecast_log', tag_columns=['Table'])
            else:
                client    = InfluxDBClient_V2(url=self._host+":"+str(self._port), token=self._token, org=self._org)
                self._verifyDB(client)
                write_api = client.write_api()
                write_api.write(self._database, record=df,     data_frame_measurement_name=data.SQLTable, retention_policy=self._retention)
                write_api.write(self._database, record=df_log, data_frame_measurement_name='forecast_log', data_frame_tag_columns=['Table'], retention_policy=self._retention)
                write_api.close()
                client.close()
 
    def getLastIssueTime(self, table):
        """
        Get last issue time (stored in measurement 'forecast_log' and tagged with 'table')
        """
        IssueTime = None
        if not self._influx_V2:
            client = InfluxDBClient(host=self._host, port=self._port, database=self._database, username=self._username, password=self._password)
            self._verifyDB(client)
            select = client.query("""SELECT Last("IssueTime") AS "IssueTime" FROM "forecast_log" WHERE "Table"='""" + table + """'""")
            for row in select.get_points():
                IssueTime = row['IssueTime']
        else:
            client    = InfluxDBClient_V2(url=self._host+":"+str(self._port), token=self._token, org=self._org)
            self._verifyDB(client)
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
            IssueTime = datetime.fromtimestamp(IssueTime, tz=timezone.utc)
        else:
            IssueTime = datetime(1990, 1, 1, 0, 0, 0, 0,timezone.utc)
        return(IssueTime)

    def getData(self, start, table):
        """
        Get data from Influx repository. Note that no data aggregation is performed.
        That is, we assume all fields are stored for each timestamp.

        start   start time of query (data will be returned to end of database)
        table   measurement, for which all fields are to be returned
        """
        try:
            startTime = start.strftime('%Y-%m-%dT%H:%M:%SZ')
            if not self._influx_V2:
                client    = InfluxDBClient(host=self._host, port=self._port, database=self._database, username=self._username, password=self._password)
                self._verifyDB(client)
                sql       = 'SELECT * FROM "' + table + '" WHERE time >= ' + "'" + startTime + "'"
                select    = client.query(sql)
                history   = pd.DataFrame(select.get_points())
                if not history.empty:
                    history.rename(columns={"time": "periodEnd"}, inplace=True)
                    history['periodEnd'] = pd.to_datetime(history['periodEnd'])
                    history.set_index("periodEnd", inplace=True)
            else:
                client    = InfluxDBClient_V2(url=self._host+":"+str(self._port), token=self._token, org=self._org)
                self._verifyDB(client)
                query_api = client.query_api()
                history   = query_api.query_data_frame(f'from(bucket:"{self._database}") ' +
                                                   f'  |> range(start: {startTime}) ' +
                                                   f'  |> filter(fn: (r) => r._measurement == "{table}") ' +
                                                   f'  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")')
                if not history.empty:
                    history.drop(columns=['result', 'table', '_start', '_stop', '_measurement'], inplace=True)
                    history.rename(columns={"_time": "periodEnd"}, inplace=True)
                    history.set_index("periodEnd", inplace=True)
            return history

        except Exception as e:
            print("Warning - getData: " + str(e))
            return pd.DataFrame()

    def _verifyDB(self, client):
        """verify, whether database (bucket) exists - if not, create it"""
        if not self._influx_V2:
            select = client.query("show databases")
            db     = pd.DataFrame(select.get_points())
            if self._database not in db['name'].values:
                client.create_database(self._database)
        else:
            buckets_api = client.buckets_api()
            if buckets_api.find_bucket_by_name(self._database) is None:
                buckets_api.create_bucket(bucket_name = self._database, org = self._org)

    # ----------------------------------------------------------------------------------- outdated code
    def getPostData(self, solcast, power_field):
        """get data to be posted to SolCast - deprecated as SolCast deprecated data upload"""
        try:
            if self._influx_V2:
                sys.tracebacklimit=0
                raise Exception("Solcast post not supported for Influx V2 databases")
            endTime   = datetime.fromisoformat(solcast.IssueTime)
            delta_t   = round((endTime - solcast.last_issue).total_seconds()/60)         # delta_t = time since last IssueTime
            if delta_t > 14400: delta_t = 1440                                           # limit to 1 days (in case of downtime)
            endTime   = endTime - timedelta(minutes=5)                                   # keep last 5min interval for next call ...
            startTime = endTime - timedelta(minutes=delta_t)

            endTime   = endTime.strftime('%Y-%m-%dT%H:%M:%SZ')
            startTime = startTime.strftime('%Y-%m-%dT%H:%M:%SZ')

            meas, field = self.config['Influx'].get(power_field).split('.')

            client      = InfluxDBClient(host=self._posthost, port=self._port, database=self._postdatabase, username=self._username, password=self._password)
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
            print("Warning - getPostData: " + str(e))
            return(None)
