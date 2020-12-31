from influxdb import DataFrameClient
import pandas as pd
import numpy as np

from .forecast import Forecast

class InfluxRepo:
    def __init__(self, config):
        self.config = config

    def loadData(self, data: Forecast):
        if (data.InfluxFields):
            myHost     = self.config['Influx'].get('host')
            myPort     = self.config['Influx'].getint('port', 8086)
            myDatabase = self.config['Influx'].get('database')
            myClient   = DataFrameClient(host=myHost, port=myPort, database=myDatabase)
            myClient.write_points(data.DataTable[data.InfluxFields], data.SQLTable)
