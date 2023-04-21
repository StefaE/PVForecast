"""
Copyright (C) 2022    Stefan Eichenberger   se_misc ... hotmail.com

This file is part of the PVOptimize and PVForecast project: you can 
redistribute it and/or modify it under the terms of the GNU General 
Public License as published by the Free Software Foundation, either 
version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import warnings
_pvlib_installed = True
try:
    import pvlib
    from pvlib.pvsystem    import PVSystem
    from pvlib.location    import Location
    from pvlib.modelchain  import ModelChain
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=UserWarning, message=r'.*highly experimental.*')
        from pvlib.forecast    import ForecastModel
    from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS
    from pvlib             import irradiance
    if pvlib.__version__ < '0.9.0':
        _pvlib_installed = False                                                         # we need at least 0.9.0
    pass
except:
    _pvlib_installed = False
    pass

import pandas as pd
import numpy  as np
import re
import sys

from .forecast    import Forecast

class PVModel(Forecast):
    """Model PV output based on irradiance or cloud coverage data"""
    __operational__ = _pvlib_installed

    def __init__(self, config, section = 'PVSystem'):
        """Initialize PVModel
        config      configparser object with section [<section>]
                    <section> defaults to 'PVSystem'"""

        try:
            self._pvversion = pvlib.__version__
            if self._pvversion > '0.9.4':
                print("Warning --- pvmodel not tested with pvlib > 0.9.4")
            elif self._pvversion < '0.9.0':
                sys.tracebacklimit=0
                raise Exception("ERROR --- require pvlib >= 0.9.0")
            super().__init__()
            self.config = config
            self._cfg   = section
            self.config['DEFAULT']['NominalEfficiency']  =  '0.96'                       # nominal inverter efficiency, default of pvwatts model
            self.config['DEFAULT']['TemperatureCoeff']   = '-0.005'                      # temperature coefficient of module, default of pvwatts model
            self.config['DEFAULT']['TemperatureModel']   = 'open_rack_glass_glass'       # https://pvlib-python.readthedocs.io/en/stable/generated/pvlib.temperature.sapm_cell.html
            self.config['DEFAULT']['clearsky_model']     = 'simplified_solis'            # default clearsky model
            self.config['DEFAULT']['Altitude']           = '0'                           # default altitude sea level
            self.config['DEFAULT']['Model']              = 'PVWatts'                     # default PV modeling stratey
            if section != 'PVSystem':
                for item in list(self.config.items('PVSystem')):                         # copy 'PVSystem' into default, so that it serves as fallback for 'PVSystem_i' (split-arrays)
                    self.config['DEFAULT'][item[0]] = item[1]

            self._location = Location(latitude  = self.config[self._cfg].getfloat('Latitude'),
                                      longitude = self.config[self._cfg].getfloat('Longitude'), 
                                      altitude  = self.config[self._cfg].getfloat('Altitude'),
                                      tz='UTC')                                          # let's stay in UTC for the entire time ...
            self._pvsystem          = None                                               # PV system, once defined with init_CEC() or init_PVWatts()
            self._mc                = None                                               # Model chain, once defined in init_CEC() or init_PVWatts()
            self._weather           = None                                               # weather data used for getIrradiance() and runModel()
            self.irradiance_model   = None                                               # model name if irradiance data calculated in getIrradiance()
            self.irradiance         = None                                               # calculated irradiance data
            self.pv_model           = None                                               # CEC or PVWatts once solar system is defined
            self.SQLTable           = self._cfg.lower()                                  # which SQL table name is this data stored to (see DBRepository.loadData())
            self.storePath          = self.config[self._cfg].get('storePath')            # where to store .csv file


            if (self.config[self._cfg].get('Model') == 'CEC'):
                self._init_CEC()
            else:
                self._init_PVWatts()

        except Exception as e:
            print("pvmodel __init__: " + str(e))
            sys.exit(1)

    def _init_CEC(self):
        """Configure PV system based on actual components available in pvlib CEC database"""

        try:
            moduleName     = self.config[self._cfg].get('ModuleName')
            inverterName   = self.config[self._cfg].get('InverterName')
            tempModel      = self.config[self._cfg].get('TemperatureModel')
            self._pvsystem = PVSystem(surface_tilt                 = self.config[self._cfg].getfloat('Tilt'),
                                      surface_azimuth              = self.config[self._cfg].getfloat('Azimuth'),
                                      module_parameters            = pvlib.pvsystem.retrieve_sam('cecmod')[moduleName],
                                      inverter_parameters          = pvlib.pvsystem.retrieve_sam('cecinverter')[inverterName],
                                      strings_per_inverter         = self.config[self._cfg].getint('NumStrings'),
                                      modules_per_string           = self.config[self._cfg].getint('NumPanels'),
                                      temperature_model_parameters = TEMPERATURE_MODEL_PARAMETERS['sapm'][tempModel])
            self._mc       = ModelChain(self._pvsystem, self._location, aoi_model='physical', spectral_model='no_loss')
            self.pv_model  = 'CEC'
        except Exception as e:
            print("init_CEC: " + str(e))
            sys.exit(1)

    def _init_PVWatts(self):
        """Configure PV system using simplified PVWatts model"""

        try:
            pvwatts_module   = { 'pdc0'         : self.config[self._cfg].getfloat('SystemPower'),
                                 'gamma_pdc'    : self.config[self._cfg].getfloat('TemperatureCoeff') }
            pvwatts_inverter = { 'pdc0'         : self.config[self._cfg].getfloat('InverterPower'), 
                                 'eta_inv_nom'  : self.config[self._cfg].getfloat('NominalEfficiency') }
            pvwatts_losses   = { 'soiling'    : 0,   'shading': 0, 'snow':            0, 'mismatch': 0, 'wiring':       2, 
                                 'connections': 0.5, 'lid'    : 0, 'nameplate_rating':0, 'age':      0, 'availability': 0 }
            tempModel        = self.config[self._cfg].get('TemperatureModel')
            self._pvsystem   = PVSystem(surface_tilt                 = self.config[self._cfg].getfloat('Tilt'),
                                        surface_azimuth              = self.config[self._cfg].getfloat('Azimuth'),
                                        module_parameters            = pvwatts_module,
                                        inverter_parameters          = pvwatts_inverter,
                                        losses_parameters            = pvwatts_losses,
                                        temperature_model_parameters = TEMPERATURE_MODEL_PARAMETERS['sapm'][tempModel])
            self._mc          = ModelChain.with_pvwatts(self._pvsystem, self._location,
                                        dc_model='pvwatts', ac_model='pvwatts',
                                        aoi_model='physical', spectral_model='no_loss')
            self.pv_model    = 'PVWatts'
        except Exception as e:
            print("init_PVWatts: " + str(e))
            sys.exit(1)

    def getIrradiance(self, weather: Forecast, model='disc'):
        """Get irradiance data from weather files (see DWDForecast()) using various models
        weather             object created by one of the subclasses of Forecast. weather.weatherData
                            must contain: weather.DataTable, weather.IssueTime
                            Columns in wheather.DataTable must include:
                                'temp_air', 'temp_dew' : Air and dew point temperature [K]
                                'wind_speed'           : [km/h]
                                'pressure'             : [Pa]
                            For irradiation based models:
                                'ghi'                  : W/m2
                            For cloud based models 'campbell_norman' and 'clearsky_scaling':
                                'clouds'               : 0 .. 100 [%]

        model               one of: 'disc', 'dirint', 'dirindex', 'erbs'     (GHI decomposition models)
                                    'campbell_norman', 'clearsky_scaling'    (cloud coverage to irradiance)
                                    'clearsky'                               (clear sky model)
        cloud_cover_param   name of cloud cover parameter in weather"""

        try:
            try:                                                                         # if weather is a Forecast object, this will work
                weatherData    = weather.DataTable                                       # extract weather data table from weather
                self.IssueTime = weather.IssueTime
                if (weather.SQLTable == 'dwd_s'):                                        # we want be able to distinguish MOSMIX_L and _S data
                    self.SQLTable = self._cfg.lower() + '_s'
            except AttributeError:                                                       # we only have weather data ... let's try anyway
                weatherData    = weather 
            if (model not in ['clearsky', 'clearsky_scaling', 'campbell_norman']):       # we don't need this for cloud models ...
                if 'ghi' not in weatherData:
                    sys.tracebacklimit=0
                    raise Exception('ERROR --- weather does not include irradiation data, use cloud based models instead of = ' + model)
                ghi      = np.array(weatherData['ghi'])
                solar_position = self._location.get_solarposition(times       = weatherData.index,
                                                                  pressure    = weatherData['pressure'],
                                                                  temperature = weatherData['temp_air'] - 273.15)
                cosSZA         = np.cos(solar_position['zenith']*np.pi/180)
            if (model == 'disc' or model == 'dirint' or model == 'dirindex'):
                if (model == 'disc'):
                    disc = pvlib.irradiance.disc(ghi              = ghi,                 # returns dataframe with columns = ['dni', 'kt', 'airmass']
                                                 solar_zenith     = solar_position['zenith'],
                                                 datetime_or_doy  = weatherData.index,
                                                 pressure         = weatherData['pressure'])
                    dni  = np.array(disc['dni'])
                    kt   = np.array(disc['kt'])
                elif (model == 'dirint'):
                    dni  = pvlib.irradiance.dirint(ghi            = ghi,                 # returns array
                                                   solar_zenith   = solar_position['zenith'],
                                                   times          = weatherData.index,
                                                   temp_dew       = weatherData['temp_dew'] - 273.15)
                else:
                    clearsky = self._location.get_clearsky(weatherData.index,            # calculate clearsky ghi, dni, dhi for times
                                                           model='ineichen')
                    dni  = pvlib.irradiance.dirindex(ghi          = ghi,                 # returns array
                                                     ghi_clearsky = clearsky['ghi'],
                                                     dni_clearsky = clearsky['dni'],
                                                     zenith       = solar_position['zenith'],
                                                     times        = weatherData.index,
                                                     pressure     = weatherData['pressure'],
                                                     temp_dew     = weatherData['temp_dew'] - 273.15)
                dhi = ghi - dni*cosSZA
            elif (model == 'erbs'):
                erbs = pvlib.irradiance.erbs(ghi             = ghi,                  # returns dataframe with columns ['dni', 'dhi', 'kt']
                                             zenith          = solar_position['zenith'],
                                             datetime_or_doy = weatherData.index)
                dni  = np.array(erbs['dni'])
                dhi  = np.array(erbs['dhi'])
                kt   = np.array(erbs['kt'])
            elif (model == 'clearsky'):
                clearsky_model  = self.config[self._cfg].get('clearsky_model')
                self.irradiance = self._location.get_clearsky(weatherData.index,         # calculate clearsky ghi, dni, dhi for clearsky
                                                              model=clearsky_model)
            elif (model == 'clearsky_scaling' or model == 'campbell_norman'):
                fcModel = ForecastModel('dummy', 'dummy', 'dummy')                       # only needed to call methods below
                fcModel.set_location(latitude=self._location.latitude, longitude=self._location.longitude, tz=self._location.tz)
                self.irradiance = fcModel.cloud_cover_to_irradiance(weatherData['clouds'], how = model)
            else:
                sys.tracebacklimit=0
                raise Exception("ERROR --- incorrect irradiance model called: " + model)
        except Exception as e:
            print("getIrradiance: " + str(e))
            sys.exit(1)

        if (model != 'clearsky' and model != 'clearsky_scaling' and model != 'campbell_norman'):
            self.irradiance         = pd.DataFrame(data=[ghi, dni, dhi]).T
            self.irradiance.index   = weatherData.index
            self.irradiance.columns = ['ghi', 'dni', 'dhi']
        if (model == 'disc' or model == 'erbs'):
            self.irradiance['kt']   = kt
        self.irradiance_model       = model
        try:
            self.irradiance         = pd.concat([weatherData['temp_air'] - 273.15, weatherData['wind_speed'], self.irradiance], axis=1)
        except:
            pass

    def runModel(self, weather: Forecast, model, modelLst = 'all'):
        """Run one PV simulation model (named in self.pv_model, set in getIrradiance())
        Weather data is inherited from prior call to getIrradiance() call
        Populates self.sim_result      pandas dataframe with simulation results"""

        if modelLst is not None:
            modelLst     = modelLst.lower()
            if modelLst != 'all' and model != modelLst:                                   # we have an explict list of models to calculate
                modelLst = modelLst.replace(" ", "")
                models   = modelLst.split(",")
                if model not in models:                                                   # request was for something else ...
                    return None

        try:
            model = model.lower()
            self.getIrradiance(weather, model)
            self._mc.run_model(self.irradiance)
            cols = ['ghi', 'dni', 'dhi']
            if 'kt' in self.irradiance: 
                cols.append('kt')
            if (self.pv_model == 'PVWatts'):
                self.DataTable = pd.concat([self._mc.results.dc, self._mc.results.ac, self.irradiance[cols]], axis=1)
            else:                                                                        # CEC
                self.DataTable = pd.concat([self._mc.results.dc.p_mp, self._mc.results.ac, self.irradiance[cols]], axis=1)
            m                  = self.irradiance_model
            if (m == 'disc' or m == 'erbs'):
                self.DataTable.columns = ['dc_' + m, 'ac_' + m, 'ghi_' + m, 'dni_' + m, 'dhi_' + m, 'kt_' + m]
            else:
                self.DataTable.columns = ['dc_' + m, 'ac_' + m, 'ghi_' + m, 'dni_' + m, 'dhi_' + m]
            self.InfluxFields.append('dc_' + m)
            return self.DataTable

        except Exception as e:
            print("runModel: " + str(e))
            sys.exit(1)

    def run_allModels(self, weather: Forecast, modelLst = 'all'):
        """Run all implemented models (default). Alternatively, 'modelLst' can contain a 
        comma separated list of valid models (see self.runModel()) to be calculated
        
        Populates self.DataTable   pandas dataframe with all simulation results"""

        dfList = []                                                                      # list of calculated models
        if 'ghi' in weather.DataTable:                                                   # ---- irrandiance based models
            dfList.append(self.runModel(weather, 'disc',     modelLst))
            dfList.append(self.runModel(weather, 'dirint',   modelLst))
            dfList.append(self.runModel(weather, 'dirindex', modelLst))
            dfList.append(self.runModel(weather, 'erbs',     modelLst))
        if 'clouds' in weather.DataTable:
            dfList.append(self.runModel(weather, 'clearsky_scaling', modelLst))          # ---- cloud based models
            dfList.append(self.runModel(weather, 'campbell_norman', modelLst))
        dfList.append(self.runModel(weather, 'clearsky', modelLst))
        dfList.append(self._mc.results.solar_position.zenith)                            # ---- add solar position
        self.DataTable = pd.concat(dfList, axis=1)
        drop           = []
        for col in self.DataTable:
            if 'ghi' in col and not (col.startswith('ghi_clearsky') or col.startswith('ghi_campbell')):
                drop.append(col)                                                         # ghi is input and available from weather data section in output
        if (len(drop) > 0): self.DataTable = self.DataTable.drop(drop, axis=1)
        
    def run_splitArray(self, weather: Forecast, modelLst = 'all'):
        try:
            if self._cfg != 'PVSystem':
                sys.tracebacklimit=0
                raise Exception ("ERROR --- run_splitArray can only be called on lead array 'PVSystem', not " + self._cfg)
            self.run_allModels(weather, modelLst)
            pat       = re.compile('^PVSystem_')
            followers = [elem for elem in self.config.sections() if pat.match(elem)]

            if len(followers) > 0:                                                       # we have a split-array configuration
                storage        = self.config['PVSystem'].get('storage', 'sum').lower()   # 'individual', 'both' or 'sum'
                pat            = re.compile('^(ac|dc)_')                                 # PV output cols match this regex
                output         = [ c for c in list(self.DataTable) if pat.match(c)]
                if storage == 'individual' or storage == 'both':
                    suffix     = '_' + self.config['PVSystem'].get('suffix', '1')        # determine suffix of first measurement
                    rename     = { c : c + suffix for c in output }
                    if storage == 'individual':
                        self.DataTable.rename(columns = rename, inplace = True)          # rename columns to contain suffix
                    else:                                                                # initialize a copy of the output columns
                        df     = self.DataTable[output].copy()
                        df.rename(columns = rename, inplace = True)
                        self.DataTable    = self.DataTable.join(df, how='inner')         # this basically duplicates output columns; we'll add follower results to base cols (without suffix)

                for elem in followers:
                    pv         = PVModel(self.config, elem)
                    pv.run_allModels(weather, modelLst)
                    df         = pv.DataTable[output].copy()                             # get only output columns
                    if storage == 'both' or storage == 'sum':
                        self.DataTable[output] = self.DataTable[output] + df             # add new values to existing sum
                        pass
                    if storage == 'individual' or storage == 'both':
                        suffix = re.search('_.+$', elem).group(0)                        # must match, since we built 'followers' based on 'PVSystem_' regex
                        rename = { c : c + suffix for c in output }
                        df.rename(columns = rename, inplace = True)                      # rename columns to contain suffix
                        self.DataTable = self.DataTable.join(df, how = 'inner')          # ... and join up

                pat = re.compile('^dc_')
                self.InfluxFields = [ c for c in self.DataTable.columns if pat.match(c)]
                pass

        except Exception as e:
            print ("run_splitArray: " + str(e))
            sys.exit(1)
        