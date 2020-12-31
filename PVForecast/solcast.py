from pysolcast.rooftop import RooftopSite
from datetime          import datetime, timezone
from suntime           import Sun, SunTimeException
try:
    import nonesense
except ImportError:
    print("nonesense not installed")

import pandas as pd
import numpy  as np
import re
import sys
import pickle                                                                            # used for debugging only

from .forecast import Forecast
from .dbrepository import DBRepository

class SolCast(Forecast):
    def __init__(self, config):
        """Initialize PVModel
        config      configparser object with section [SolCast]"""

        super().__init__()
        self.config    = config
        repository_id  = self.config['SolCast'].get('repository_id')
        api_key        = self.config['SolCast'].get('api_key')
        self._site     = RooftopSite(api_key, repository_id)
        self._interval = self.config['SolCast'].getint('interval', 60) - 2               # set default polling interval to 60min, 2min slack in case we have hourly crontab
        self._db       = None                                                            # DBRepository object once DB is opened
        self.SQLTable  = 'solcast'

    def _doDownload(self):
        latitude       = self.config['SolCast'].getfloat('Latitude')
        longitude      = self.config['SolCast'].getfloat('Longitude')
        sun            = Sun(latitude, longitude)
        today_sr       = sun.get_sunrise_time()
        today_ss       = sun.get_sunset_time()
        now_utc        = datetime.now(timezone.utc)
        retVal         = False
        if (self.config['SolCast'].getboolean('enable') and self.config['SolCast'].getboolean('storeDB')):
            if (now_utc > today_sr and now_utc < today_ss):                              # storeDB enabled, SolCast enabled, daylight
                self._db   = DBRepository(self.config)
                last_issue = self._db.getLastIssueTime(self.SQLTable)
                delta_t    = round((now_utc - last_issue).total_seconds()/60)
                if (delta_t > self._interval):                                           # download SolCast again
                    retVal = True
                    print("Message - downloading SolCast data at (UTC): " + str(now_utc))
        return(retVal)

    def getSolCast(self):
        if (self._doDownload()):
            forecasts = self._site.get_forecasts_parsed()

            # --------- debugging begin
            #myFile    = open('./temp/forecasts_01', 'wb')
            #pickle.dump(forecasts, myFile)
            #myFile.close()
            #
            #myFile    = open('./temp/forecasts_demo_02', 'rb')
            #forecasts = pickle.load(myFile)
            #myFile.close()
            # --------- debugging end

            df                = pd.DataFrame(forecasts['forecasts'])
            df                = df.set_index('period_end')
            df.index.name     = 'PeriodEnd'
            self.DataTable    = df.drop('period', axis=1)*1000                           # convert kWh to Wh
            self.IssueTime    = str(self.DataTable.index[0] - df['period'][0])
            self.InfluxFields = self.get_ParaNames()
            self._db.loadData(self)                                                      # store data in repository
            del self._db
            self._db          = None