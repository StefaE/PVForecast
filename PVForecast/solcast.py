from pysolcast.rooftop import RooftopSite
from datetime          import datetime, timezone
from astral            import LocationInfo
from astral.sun        import sun

import pandas as pd
import re
import sys
import pickle                                                                            # used for debugging only

from .forecast     import Forecast
from .dbrepository import DBRepository
from .influx       import InfluxRepo

class SolCast(Forecast):
    def __init__(self, config):
        """Initialize PVModel
        config      configparser object with section [SolCast]"""

        super().__init__()
        self.config       = config
        resource_id       = self.config['SolCast'].get('resource_id')
        resource_id_2     = self.config['SolCast'].get('resource_id_2', None)            # 2nd resource_id for split array installations
        api_key           = self.config['SolCast'].get('api_key')
        self._site        = RooftopSite(api_key, resource_id)
        if resource_id_2 is not None: self._site_2 = RooftopSite(api_key, resource_id_2)
        else:                         self._site_2 = None
        self._interval    = self.config['SolCast'].getint('interval', 60) - 2            # set default polling interval to 60min, 2min slack in case we have hourly crontab
        self._db          = None                                                         # DBRepository object once DB is opened
        self._storeDB     = self.config['SolCast'].getboolean('storeDB', 0)              # ... store to DB
        self._storeInflux = self.config['SolCast'].getboolean('storeInflux')             # ... store to Influx (one of the two must be true to make sense to get data from solcast)
        self._force       = self.config['SolCast'].getboolean('force', False)            # force download - note that we are restricted in number of downloads/day
        if self._force:
            print("Warning --- SolCast download forced!!! Note limits in number of downloads/day!")
        self.SQLTable     = 'solcast'
        self.postDict     = None                                                         # dictionary to post to solcat

    def _doDownload(self):
        latitude       = self.config['SolCast'].getfloat('Latitude')
        longitude      = self.config['SolCast'].getfloat('Longitude')
        location       = LocationInfo('na', 'na', 'UTC', latitude=latitude, longitude=longitude)
        now_utc        = datetime.now(timezone.utc)
        mySun          = sun(location.observer, date=now_utc)
        retVal         = False
        if self._force or (now_utc > mySun['sunrise'] and now_utc < mySun['sunset']):    # storeDB enabled, SolCast enabled, daylight
            if self._storeDB or self._storeInflux:
                if self._storeDB:
                    self._db        = DBRepository(self.config)
                    self.last_issue = self._db.getLastIssueTime(self.SQLTable)
                    if self._storeInflux: self._influx = InfluxRepo(self.config)         # need to open Influx to later load data
                else:
                    self._influx    = InfluxRepo(self.config)
                    self.last_issue = self._influx.getLastIssueTime(self.SQLTable)
                delta_t          = round((now_utc - self.last_issue).total_seconds()/60)
                if self._force or delta_t > self._interval:                              # download SolCast again
                    retVal = True
                    print("Message - downloading SolCast data at (UTC): " + str(now_utc))
            else:
                print("Warning --- getting SolCast data not supported without database storage enabled (storeDB or storeInflux)")
        return(retVal)

    def getSolCast(self):
        if (self._doDownload()):
            try:
                forecasts_1 = self._site.get_forecasts_parsed()
                if self._site_2 is not None: 
                    forecasts_2 = self._site_2.get_forecasts_parsed()
            except Exception as e:
                print ("getSolCast: " + str(e))
                sys.exit(1)

            # --------- debugging begin
            #myFile    = open('./temp/forecasts_01', 'wb')                               # store forecast to file for later debugging runs 
            #pickle.dump(forecasts, myFile)
            #myFile.close()
            #
            # myFile      = open('./temp/forecasts_demo_02', 'rb')                           # load dummy solcast forecast for debugging
            # forecasts_1 = pickle.load(myFile)
            # forecasts_2 = forecasts_1
            # myFile.close()
            # --------- debugging end

            df                  = pd.DataFrame(forecasts_1['forecasts'])
            df                  = df.set_index('period_end')
            period              = df['period'][0]
            df.drop('period', axis=1, inplace=True)
            if self._site_2 is not None:
                cols            = list(df)
                df.columns      = [str(c) + '_1' for c in cols]
                df_2            = pd.DataFrame(forecasts_2['forecasts'])
                df_2            = df_2.set_index('period_end')
                df_2.drop('period', axis=1, inplace=True)
                df_2.columns    = [str(c) + '_2' for c in cols]
                df              = pd.merge(df, df_2, on='period_end', how='inner')
                for c in cols:
                    df[c]       = df[c + '_1'] + df[c + '_2']
            df.index.name       = 'PeriodEnd'
            self.DataTable      = df*1000                                                # convert kWh to Wh
            self.IssueTime      = str(self.DataTable.index[0] - period)
            self.InfluxFields   = self.get_ParaNames()
            if self._storeDB: self._db.loadData(self)                                    # store data in repository, db was opened in self._doDownload()
            if self.config['SolCast'].getboolean('storeInflux'):
                self._influx.loadData(self)                                              # store data to Influx, client was opened in self._doDownload()
                if self.config['SolCast'].getboolean('post', 0):
                    self.postDict = self._influx.getPostData(self)
                    if self.postDict is not None:
                        if self._storeDB:
                            myPost           = Forecast()
                            myPost.DataTable = pd.DataFrame.from_dict(self.postDict['measurements'])[['period_end', 'total_power']]
                            myPost.DataTable['period_end'] = pd.to_datetime(myPost.DataTable['period_end'])
                            myPost.DataTable.rename(columns={'period_end' : 'PeriodEnd'}, inplace=True)
                            myPost.DataTable.set_index('PeriodEnd', inplace=True)
                            myPost.IssueTime = self.IssueTime
                            myPost.SQLTable  = self.SQLTable + '_post'
                            self._db.loadData(myPost)
                        try:
                            self._site.post_measurements(self.postDict)
                        except Exception as e:
                            print ("getSolCast/post: " + str(e))
                        pass
            if self._storeDB: 
                del self._storeDB
                self._storeDB = None
