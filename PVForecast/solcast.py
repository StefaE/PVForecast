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
        resource_id     = self.config['SolCast'].get('resource_id')
        api_key           = self.config['SolCast'].get('api_key')
        self._site        = RooftopSite(api_key, resource_id)
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
                if (delta_t > self._interval):                                           # download SolCast again
                    retVal = True
                    print("Message - downloading SolCast data at (UTC): " + str(now_utc))
            else:
                print("Warning --- getting SolCast data not supported without database storage enabled (storeDB or storeInflux)")
        return(retVal)

    def getSolCast(self):
        if (self._doDownload()):
            forecasts = self._site.get_forecasts_parsed()

            # --------- debugging begin
            #myFile    = open('./temp/forecasts_01', 'wb')                               # store forecast to file for later debugging runs 
            #pickle.dump(forecasts, myFile)
            #myFile.close()
            #
            #myFile    = open('./temp/forecasts_01', 'rb')                           # load dummy solcast forecast for debugging
            #forecasts = pickle.load(myFile)
            #myFile.close()
            # --------- debugging end

            df                = pd.DataFrame(forecasts['forecasts'])
            df                = df.set_index('period_end')
            df.index.name     = 'PeriodEnd'
            self.DataTable    = df.drop('period', axis=1)*1000                           # convert kWh to Wh
            self.IssueTime    = str(self.DataTable.index[0] - df['period'][0])
            self.InfluxFields = self.get_ParaNames()
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
