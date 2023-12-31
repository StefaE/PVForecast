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

Emission factors are taken from https://www.electricitymaps.com/, which
provides them under the MIT License. See License File in subdirectory
./emissionFactors for details.
"""

import pandas as pd
_scipy_installed = True
try:
    from scipy import stats
except:
    _scipy_installed = False
import json
import requests
import os
import sys
import yaml
from datetime import datetime, timedelta, timezone
_entso_installed = True
try:
    from entsoe import EntsoePandasClient
except:
    _entso_installed = False                                                             # if we don't config to use Entso-E, we only get a warning ...

from .forecast import Forecast
from .influx   import InfluxRepo

class EntsoE(Forecast):
    """Class for managing Entso-E data from transparency.entsoe.eu"""
    __operational__ = _entso_installed

    def __init__(self, config, _start = None):
        """Initialize Entso-E
        config      configparser object with section [Entso-E]"""
        if not _entso_installed: 
            print('Error Entso-E: library entsoe not available')
            sys.exit(1)

        super().__init__()
        self.config       = config
        self.SQLTable     = 'entsoe'
        self.storePath    = self.config['Entso-E'].get('storePath')

        zoneLst           = self.config['Entso-E'].get('zones')
        zoneLst           = zoneLst.replace(" ", "")
        self.zones        = zoneLst.split(",")

        self.reportLst    = ['load', 'genForecast', 'renewDayAhead', 'renewIntraday', 'genActual', 'prices']
        api_key           = self.config['Entso-E'].get('api_key')
        self.client       = EntsoePandasClient(api_key=api_key)

        self._verbose     = self.config['Entso-E'].getint('verbose', 0)

        self._entso       = {}
        self._cols        = {}
        self._lastIdx     = {}
        self._slope       = {}
        self._intercept   = {}
        for zone in self.zones:                                                          # default 'model' for co2 forecast:
            self._slope[zone]     = 1                                                    # linear identity
            self._intercept[zone] = 0

        self.csvName      = None

        self._start       = None
        self._end         = None
        self._now         = pd.Timestamp.now(timezone.utc)                               # default, if 'start' and 'end' are not defined         

        if _start is not None:                                                           # this is used if the caller loops over a range of dates
            self._start   = _start
        elif self.config['Entso-E'].get('start') is not None:                            # this is used if config file defines 'start'
            self._start   = pd.Timestamp(self.config['Entso-E'].get('start'), tz='UTC')
        if self._start is not None:
            self._verbose = 2
            if self._start < self._now:                                                  # config file defines 'start' in the past
                self._now = self._start                                                  # will be overwritten if 'end' is also defined; if not we pretend 'now' = 'start'
        self._start   = self._now - timedelta(days=1)                                    # we go back one day, to update CO2 (from generated data) with late data

        if self.config['Entso-E'].get('end') is not None and _start is None:             # this is used if config file defines 'end'
            self._end     = pd.Timestamp(self.config['Entso-E'].get('end'),   tz='UTC')  
            if self._end > pd.Timestamp.now(timezone.utc).normalize() + timedelta(days=1):
                self._now = pd.Timestamp.now(timezone.utc).normalize()
                self._end = self._now.normalize() + timedelta(days=1) 
            else:
                self._now = self._end.normalize() - timedelta(days=1)
        else:
            self._end     = self._now.normalize() + timedelta(days=2)                    # ... until end of day ahead
        self._start       = self._start.round('15min')
        self._end         = self._end.round('15min')

        if self._verbose > 1:
            print('Entso-E Message: start = ' + str(self._start) + ', end = ' + str(self._end) + ', now = ' + str(self._now))
        if self._start > self._end:
            print('Entso-E Error: Incorrect time interval selected: start > end')
            sys.exit(1)

        self._modelDays   = self.config['Entso-E'].get('modelDays', 7)
        if _scipy_installed:
            if self._end - self._start > timedelta(days=self._modelDays):
                print("Warning Entso-E: Model building inaccurate, as it spans " + str(self._end - self._start))
            self._buildModelCO2()
        else:
            print('Warning Entso-E: Model building not possible without installed library scipy')
        return

    def prepareDump(self, zone):
        self.csvName      = 'EntsoE_' + zone + '_' + self.IssueTime[:16].replace(' ', '_').replace(':', '-') + '.csv.gz'
        self.SQLTable     = 'entsoe_' + zone
        self.DataTable    = self._entso[zone]
        if self.DataTable is None: 
            return False
        else:
            self.InfluxFields = self.get_ParaNames()
            return True      

    def getData_EntsoE(self):
        for zone in self.zones:
            self._entso[zone]   = None
            self._cols[zone]    = {}
            self._lastIdx[zone] = {}
        self.IssueTime = str(self._now.round('1s'))
        ok = self._download_EntsoE()
        if ok: 
            self._mapEmissionFactors()
            self._applyModelCO2()

    def _download_EntsoE(self):
        for zone in self.zones:
            earliest = []
            for report in self.reportLst:
                df                          = None
                self._cols[zone][report]    = None
                self._lastIdx[zone][report] = {}
                try:
                    if self._verbose > 1:
                        print(" --- Entso-E downloading zone '" + zone + "', report '" + report + "' at " + pd.Timestamp.now().strftime("%Y-%m-%d, %H:%M:%S"))
                    if report == 'load':
                        df        = self.client.query_load_forecast(zone, start=self._start, end=self._end)                 # only day-ahead and actual in Entso-E
                    if report == 'genForecast':
                        df       = self.client.query_generation_forecast(zone, start=self._start, end=self._end)
                    if report == 'renewDayAhead':
                        df       = self.client.query_wind_and_solar_forecast(zone, start=self._start, end=self._end, psr_type=None)
                    if report == 'renewIntraday':
                        df       = self.client.query_wind_and_solar_forecast(zone, start=self._start, end=self._end, psr_type=None, process_type='A40')
                    if report == 'genActual':
                        df       = self.client.query_generation(zone, start=self._start, end=self._end, psr_type=None)      # 16.1.B&C
                        if isinstance(df.columns[0], tuple):                                                                # 2nd element should be 'Actual Aggregated', 'Actual Consumption'
                            delCol   = [el[1]=='Actual Consumption' for el in df.columns]                                   # find 'Consumption' columns
                            for c in df.columns[delCol]:
                                c_actual    = list(c)
                                c_actual[1] = 'Actual Aggregated'
                                c_actual    = tuple(c_actual)
                                if c_actual in df.columns:
                                    df[c_actual] = df.apply(lambda row: 0 if row[c] == row[c] and not row[c_actual] == row[c_actual] else row[c_actual] , axis=1)
                            delCol   = [idx for (idx, val) in enumerate(delCol) if val]                                     # find indices of these columns
                            df.drop(df.iloc[:, delCol], axis=1, inplace=True)                                               # ... and drop them
                            colNames = [el[0] for el in df.columns]                                                         # now we have only 'Actual Aggregated' - drop that
                            df       = df.set_axis(colNames, axis=1, copy=False)
                            df.ffill(inplace=True)                                                                          # some zones have missing values for 'Actual Aggregated' if 'Acutal Consumption' > 0
                            df.bfill(inplace=True)                                                                          # in case we have na in first row(s)
                    if report == 'prices':
                        if zone.startswith('DE') or zone=='LU': _zone = 'DE_LU'
                        else:                                   _zone = zone
                        _res = self.config['Entso-E'].get('resolution', '60T')                                              # these two zones support 15m time interval for prices
                        df       = self.client.query_day_ahead_prices(_zone, start=self._start, end=self._end, resolution = _res)

                    if df is not None:
                        if isinstance(df, pd.Series):
                            df = df.to_frame()
                        if report == 'prices':
                            df.rename(columns={df.columns[0]: 'price'}, inplace=True)
                        self._cols[zone][report]    = [report + '_' + name for name in df.columns]                          # add report type to column name
                        df              = df.set_axis(self._cols[zone][report], axis=1, copy = False)
                        self._lastIdx[zone][report] = df.last_valid_index().tz_convert('UTC')                               # end of series - in case we need replace NaN, it is up to this point

                        if report == 'renewIntraday' and self._cols[zone]['renewDayAhead'] is not None:                     # check for missing data in 'renewIntraday' (which is supposed to overwrite 'renewDayAhead')
                            df_temp = df.merge(self._entso[zone][self._cols[zone]['renewDayAhead']], how='left', left_index=True, right_index=True)
                            a  = self._cols[zone]['renewDayAhead']
                            b  = self._cols[zone]['renewIntraday']
                            a  = [a[i].replace('renewDayAhead_', '') for i in range(len(a))]
                            b  = [b[i].replace('renewIntraday_', '') for i in range(len(b))]
                            ab = list(set(a)&set(b))
                            if not (len(a) == len(b) and len(a) == len(ab)):                                                # columns between DayAhead and Intraday are not the same - drop both
                                df = None                                                                                   # we delete both as we don't know whether and if so which one is complete
                                self._entso[zone].drop(columns=self._cols[zone]['renewDayAhead'], inplace = True)
                                self._cols[zone]['renewDayAhead'] = None
                                self._cols[zone][report]          = None                                                    # renewIntraday
                                print('Warning Entso-E: missing or incomplete renewable energy forecast for zone ' + zone)
                            else:                                                                                           # check for missing data with values '0'
                                complete = True
                                for col in self._cols[zone]['renewIntraday']:
                                    col_dayAhead = col.replace('Intraday', 'DayAhead')
                                    if col_dayAhead in df_temp.columns:
                                        x     = df_temp[(df_temp[col]==0) & (df_temp[col_dayAhead]>0)][col]                 # rows which had data in 'renewDayAhead', but not in 'renewIntraday'
                                        if len(x) > 0:
                                            y_cnt = df_temp[col].groupby(df_temp.index.date).count()                        # number of rows for last day (today)
                                            x_cnt = x.groupby(x.index.date).count()                                         # count number of such rows by day, filter to last day
                                            if x_cnt.index[-1] == y_cnt.index[-1] and x_cnt[-1]/y_cnt[-1] > 0.3:            # x contains elements for last day == today and >30% of rows with renewIntraday == 0 where renewDayAhead > 0
                                                complete = False                                                            # ... looks incomplete
                                    else: complete = False  
                                if not complete:
                                    df                       = None
                                    self._cols[zone][report] = None
                                    if self._verbose > 0:
                                        print('Warning Entso-E: Incomplete renewIntraday data found for zone ' + zone)

                    if df is not None:
                        earliest.append(df.index[0])

                        if self._entso[zone] is None:
                            self._entso[zone] = df
                        else:
                            self._entso[zone] = self._entso[zone].merge(df, how = 'outer', copy = False, left_index=True, right_index=True)

                except Exception as e:
                    err = str(e)
                    if err.startswith('503') or err.startswith('404'):                                                      # we have incomplete data for at least one zone/report
                        print('Warning Entso-E - Service unavailable ' + err[:3] + '), aborted')
                        return False
                    elif self._verbose > 0:
                        if err == "":
                            err = "No data"
                        print('Error Entso-E ' + zone + " - " + report + ": " + err)

            if self._entso[zone] is not None:
                self._entso[zone] = self._entso[zone][self._entso[zone].index >= max(earliest)]
                delta_t = self._entso[zone].index[1] - self._entso[zone].index[0]                                           # add interval: Entso-E reports periodStart
                self._entso[zone].set_index(self._entso[zone].index.tz_convert('UTC') + delta_t, inplace=True)              # convert to UTC
                self._entso[zone].index.rename('periodEnd', inplace=True)
                for report in self.reportLst:
                    if self._cols[zone][report] is not None:                                                                # due to merge of reports with different time scales (15m, 1h), we may have 'NA'
                        early = pd.Timestamp('1990-01-01', tz='UTC')                                                        # the logic here may create some wrong ffill in 'genActual' if really 0-fill would be needed
                        if report == 'prices':                                                                              # ... prices are not interpolated
                            self._entso[zone].loc[early:self._lastIdx[zone][report], self._cols[zone][report]] = self._entso[zone].loc[early:self._lastIdx[zone][report], self._cols[zone][report]].ffill(limit=3)
                        else:                                                                                               # ... but physical data is interpolated
                            self._entso[zone].loc[early:self._lastIdx[zone][report], self._cols[zone][report]] = self._entso[zone].loc[early:self._lastIdx[zone][report], self._cols[zone][report]].interpolate(limit=3)
                        #self._entso[zone].loc[early:self._lastIdx[zone][report], self._cols[zone][report]].interpolate(limit=3, inplace=True)
                                                                                                                            # only interpolate 15m --> 1h, but not longer missing intervals: limit=3
        if self._verbose > 1:
            print(" --- Entso-E finished data downloading (now starting to process) at " + pd.Timestamp.now().strftime("%Y-%m-%d, %H:%M:%S"))
        return True

    def _mapEmissionFactors(self):
        with open('./emissionFactors/Mappings.json', 'r') as f:                                                             # load some mapping tables
            mappings = json.load(f)

        defaultEmissions   = mappings['defaultEmissions']
        entso_to_emissions = mappings['entso_to_emissions']
        emissionFactors    = defaultEmissions
        for zone in self.zones:
            cols  = self._cols[zone]
            entso = self._entso[zone]
            if zone in mappings['yFNameMap'].keys():
                myZone   = mappings['yFNameMap'][zone]
            else: myZone = zone
            if myZone in mappings['yFNameAvailable']:
                yFName       = myZone + '.yaml'
                _file        = './emissionFactors/' + yFName
                if (os.path.isfile(_file)):
                    _age         = os.path.getmtime(_file)
                    _age         = datetime.now(tz=timezone.utc) - datetime.fromtimestamp(_age, tz=timezone.utc)
                if (not os.path.isfile(_file)) or (_age > timedelta(days=10)):                                              # get data from: https://github.com/electricitymaps/electricitymaps-contrib/tree/master/config/zones
                    url = 'https://github.com/electricitymaps/electricitymaps-contrib/raw/master/config/zones/' + yFName
                    req = requests.get(url)
                    if req.reason != 'OK':
                        print ('Warning Entso-E: Emission data download for ' + yFName + ' failed - ' + str(req.reason))
                    else:
                        try:
                            with open(_file, 'w') as f: f.write(req.text)                                                   # write .yaml data to file, so that we have it next time
                            if self._verbose > 0:
                                print('Message Entso-E: downloaded emission factors for zone ' + myZone)
                        except Exception as e:
                            print("Warning Entso-E: Emission data can't be written: " + yFName + ": "+ str(e))

                try:
                    yFile     = open(_file, 'r')
                    yEmission = yaml.safe_load(yFile)
                    yEmission = yEmission['emissionFactors']['lifecycle']                                                   # grab life-cycle emission data
                    for emissionType in yEmission.keys():                                                               
                        if isinstance(yEmission[emissionType], dict):                                                       # ... direct value availble
                            emissionFactors[emissionType] = yEmission[emissionType]['value']
                        elif isinstance(yEmission[emissionType], list):                                                     # list of past averages of electricityMap data over previous years
                            emissionFactors[emissionType] = yEmission[emissionType][-1]['value']                            # use most recent one ...
                        else:                                                                                               # determine emission factor for each column; default factors as fall-back
                            print('Warning Entso-E: Zone ' + myZone + ' - unknown emission factor structure, using default for ' + emissionType)
                except Exception as e:
                    print ('Warning Entso-E: File ' + yFName + ' error - using default emission factors: ' + str(e))

            else:
                print('Warning Entso-E: Zone ' + zone + " - electricityMap doesn't have emission factors - using defaults")

            try:
                emission_by_cols = [defaultEmissions[entso_to_emissions[(col[len('genActual')+1:])]] for col in cols['genActual']]
                entso['calc_co2'] = entso.apply(lambda row: sum([x*y for x,y in zip(row[cols['genActual']].tolist(), emission_by_cols)])/sum(row[cols['genActual']].tolist()), axis=1)

                if cols['renewDayAhead'] is not None:                                                                       # calculate %Load, %Generation for day ahead forecasts
                    if cols['genForecast'] is not None:
                        entso['calc_pctGenerated_DayAhead'] = entso.apply(lambda row: -sum(row[cols['renewDayAhead']].tolist())/row[cols['genForecast'][0]]+1, axis=1)
                    if cols['load'] is not None:
                        entso['calc_pctLoad_DayAhead'] = entso.apply(lambda row: -sum(row[cols['renewDayAhead']].tolist())/row[cols['load'][0]]+1, axis=1)

                if cols['renewIntraday'] is not None:                                                                       # calculate %Load, %Generation for intraday forecasts
                    if cols['genForecast'] is not None:
                        entso['calc_pctGenerated_Intraday'] = entso.apply(lambda row: -sum(row[cols['renewIntraday']].tolist())/row[cols['genForecast'][0]]+1, axis=1)
                    if cols['load'] is not None:
                        entso['calc_pctLoad_Intraday'] = entso.apply(lambda row: -sum(row[cols['renewIntraday']].tolist())/row[cols['load'][0]]+1, axis=1)

                # entso.to_csv(self.storePath + zone + "_" + self.IssueTime[:16].replace(' ', '_').replace(':', '-') + '_entso_report.csv.gz', compression='gzip')           # -- for debugging
                map = {}
                if not self.config['Entso-E'].getboolean('keepRaw', False):
                    cols = [col for col in entso.columns if not(col=='prices_price' or col.startswith('load') or col.startswith('calc'))] 
                    if len(entso.columns) > len(cols):                                                                      # boil down to essential columns, drop cols
                        entso.drop(columns = cols, inplace=True)
                        for col in entso.columns:
                            map[col] = col[col.find('_')+1:].replace(' ', '_')
                        entso.rename(columns = map, inplace=True)
                        # entso.to_csv(self.storePath + zone + "_" + self.IssueTime[:16].replace(' ', '_').replace(':', '-') + '_entso_short.csv.gz',  compression='gzip')   # -- for debugging
                    else:
                        print('Error Entso-E: Zone ' + zone + ' - no essential columns to keep')
                        entso = None
                else:
                    for col in [c for c in entso.columns if c.startswith('calc')]:
                        map[col] = col[col.find('_')+1:].replace(' ', '_')
                        entso.rename(columns = map, inplace=True)

            except Exception as e:
                exception_traceback = sys.exc_info()[2]
                if entso is not None:
                    print('Warning Entso-E (line ' + str(exception_traceback.tb_lineno) + '): Incomplete data for zone ' + zone + ': ' + str(e))
                    entso.to_csv(self.storePath + zone + "_" + self.IssueTime[:16].replace(' ', '_').replace(':', '-') + '_entso_report_err.csv.gz', compression='gzip')     # -- for debugging
                else:
                    print('Warning Entso-E (line ' + str(exception_traceback.tb_lineno) + '): No data for zone ' + zone + ': ' + str(e))
                entso = None

            self._entso[zone] = entso
        return

    def _buildModelCO2(self):
        MIN_ROWS = 100
        if self.config['Entso-E'].getboolean('storeInflux', False):
            myInflux   = InfluxRepo(self.config)
            start      = self._now.normalize() - timedelta(days=self._modelDays)
            for zone in self.zones:
                history = myInflux.getData(start, f'entsoe_{zone}')
                if history.shape[0] > MIN_ROWS:                                                    # we have enough data to start building model
                    if 'pctGenerated_DayAhead' in history.columns:
                        history = history[history.index < self._now.normalize()]
                    else:
                        history = pd.DataFrame()                                                   # make sure it doesn't satisfy below IFs
                if history.shape[0] > MIN_ROWS:
                    delta_t = history.index[1] - history.index[0]
                    history['periodStart_BRU']   = history.index
                    history['periodStart_BRU']   = history['periodStart_BRU'].dt.tz_convert('Europe/Brussels') - delta_t
                    history['pctGenerated_Best'] = history.apply (lambda row: row['pctGenerated_Intraday']
                        if ('pctGenerated_Intraday' in row.index) and (not pd.isna(row['pctGenerated_Intraday']) and row['periodStart_BRU'].hour >= 8)
                        else row['pctGenerated_DayAhead'],
                        axis = 1)
                    history = history[['co2', 'pctGenerated_Best']]                                # to make .dropna not over-react
                    history.dropna(inplace=True)
                if history.shape[0] > MIN_ROWS:
                    x    = history['pctGenerated_Best'].to_numpy()
                    y    = history['co2'].to_numpy()
                    lreg = stats.linregress(x, y)
                    self._slope[zone]     = lreg.slope
                    self._intercept[zone] = lreg.intercept
                    if self._verbose > 0:
                        print('Entso-E: co2 model regenerated for zone %s - r^2 = %4.3f, slope = %8.2f, intercept = %8.2f' % (zone, lreg.rvalue**2, self._slope[zone], self._intercept[zone]))
                elif self._verbose > 0:                                                            # for now, we stay with default model
                    print('Entso-E: model creation not yet possible - insufficient historical data')
        else:
            print('Warning Entso-E: Model building not possible - requires Influx storage for historical data')
        return

    def _applyModelCO2(self):
        for zone in self.zones:
            entso = self._entso[zone]
            if entso is not None:
                entso['periodStart_BRU']   = entso.index
                delta_t = entso.index[1] - entso.index[0]
                entso['periodStart_BRU']   = entso['periodStart_BRU'].dt.tz_convert('Europe/Brussels') - delta_t
                if 'pctGenerated_DayAhead' in entso.columns:                                           # calculate 'best' estimate; deal with missing columns
                    if 'pctGenerated_Intraday' in entso.columns:
                        entso['pctGenerated_Best'] = entso.apply (lambda row: row['pctGenerated_Intraday']
                            if (not pd.isna(row['pctGenerated_Intraday']) and (row['periodStart_BRU'].hour >= 8) or pd.isna(row['pctGenerated_DayAhead']))
                            else row['pctGenerated_DayAhead'],
                            axis = 1)
                    else: entso['pctGenerated_Best'] = entso['pctGenerated_DayAhead']
                elif 'pctGenerated_Intraday' in entso.columns:
                    entso['pctGenerated_Best'] = entso['pctGenerated_Intraday']
                if 'pctGenerated_Best' in entso.columns:
                    entso['co2_forecast'] = entso['pctGenerated_Best'] * self._slope[zone] + self._intercept[zone]
                    entso.drop(columns=['periodStart_BRU', 'pctGenerated_Best'], inplace=True)
                else: entso.drop(columns=['periodStart_BRU'], inplace=True)
        return