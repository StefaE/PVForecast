import pvlib
from pvlib.pvsystem    import PVSystem
from pvlib.location    import Location
from pvlib.modelchain  import ModelChain
from pvlib.forecast    import ForecastModel
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS
from pvlib             import irradiance

import pandas as pd
import numpy  as np
import re
import sys

from .forecast    import Forecast

class PVModel(Forecast):
    """Model PV output based on irradiance or cloud coverage data"""

    def __init__(self, config, section = 'PVSystem'):
        """Initialize PVModel
        config      configparser object with section [<section>]
                    <section> defaults to 'PVSystem'"""

        try:
            self._pvversion = pvlib.__version__
            if self._pvversion > '0.8.1':
                print("Warning --- pvmodel not tested with pvlib > 0.8.1")
            elif self._pvversion < '0.8.0':
                raise Exception("ERROR --- require pvlib >= 0.8.1")
            super().__init__()
            self.config = config
            self._cfg   = section
            self.config['DEFAULT']['NominalEfficiency']  =  '0.96'                       # nominal inverter efficiency, default of pvwatts model
            self.config['DEFAULT']['TemperatureCoeff']   = '-0.005'                      # temperature coefficient of module, default of pvwatts model
            self.config['DEFAULT']['TemperatureModel']   = 'open_rack_glass_glass'       # https://pvlib-python.readthedocs.io/en/stable/generated/pvlib.temperature.sapm_cell.html
            self.config['DEFAULT']['Altitude']           = '0'                           # default altitude sea level
            self.config['DEFAULT']['Model']              = 'CEC'                         # default PV modeling stratey
            self._weatherFields = {'dwd': { 'temp_air'   : 'TTT',                        # translation: DWD parameter names --> pvlib parameter names
                                            'wind_speed' : 'FF',                         #    Note that temp_air and temp_dew are in Celsius, TTT in Kelvin
                                            'pressure'   : 'PPPP',
                                            'temp_dew'   : 'Td',
                                            'clouds'     : 'N' },
                                   'owm': { 'temp_air'   : 'temp',                       # translation: OWM parameter names --> pvlib parameter names
                                            'wind_speed' : 'wind_speed',                 #    Note that temp_air and temp_dew are in Celsius, TTT in Kelvin
                                            'pressure'   : 'pressure',
                                            'temp_dew'   : 'dew_point',
                                            'clouds'     : 'clouds' }}
            self._weatherFields['dwd_s'] = self._weatherFields['dwd']
            self._allow_experimental     = self.config[self._cfg].getboolean('experimental', False)   # needs modification of pvlib.irradiance.erbs()

            self._location = Location(latitude  = self.config[self._cfg].getfloat('Latitude'),
                                      longitude = self.config[self._cfg].getfloat('Longitude'), 
                                      altitude  = self.config[self._cfg].getfloat('Altitude'),
                                      tz='UTC')                                          # let's stay in UTC for the entire time ...
            self._pvsystem          = None                                               # PV system, once defined with init_CEC() or init_PVWatts()
            self._mc                = None                                               # Model chain, once defined in init_CEC() or init_PVWatts()
            self._weather           = None                                               # weather data used for getIrradiance() and runModel()
            self._cloud_cover_param = None                                               # weather data parameter used for cloud coverage (see _weatherFields)
            self.irradiance_model   = None                                               # model name if irradiance data calculated in getIrradiance()
            self.irradiance         = None                                               # calculated irradiance data
            self.pv_model           = None                                               # CEC or PVWatts once solar system is defined
            self.SQLTable           = self._cfg.lower()                                  # which SQL table name is this data stored to (see DBRepository.loadData())

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
            tempModel        = self.config.get(self._cfg, 'TemperatureModel')
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
        weather             object eg. created by DWDForecast.weatherData
                            must contain: weatherData.DataTable, weatherData.IssueTime
        model               one of: 'disc', 'dirint', 'dirindex', 'erbs'     (GHI decomposition models)
                                    'erbs_kt'                                (as 'erbs', but with kt as input parameter; this needs a minor
                                                                              modification to pvlib.irradiance.erbs)
                                    'campbell_norman', 'clearsky_scaling'    (cloud coverage to irradiance)
                                    'clearsky'                               (clear sky model)
        cloud_cover_param   name of cloud cover parameter in weather"""

        try:
            try:                                                                         # if weather is a Forecast object, this will work
                weatherData    = weather.DataTable                                       # extract weather data table from weather
                self.IssueTime = weather.IssueTime
                f              = self._weatherFields[weather.SQLTable]                   # field mapping dicionary weather --> pvlib
                if (weather.SQLTable == 'dwd_s'):                                        # we want be able to distinguish MOSMIX_L and _S data
                    self.SQLTable = self._cfg.lower() + '_s'
            except AttributeError:                                                       # we only have weather data ... let's try anywah
                weatherData    = weather 
                f              = {}
                for col in weatherData.columns: f[col] = col
            if ('Rad1h' not in weatherData and model not in ['clearsky', 'clearsky_scaling', 'campbell_norman']):
                raise Exception('ERROR --- weather does not include irradiation data, use cloud based models instead of = ' + model)
            elif (model not in ['clearsky', 'clearsky_scaling', 'campbell_norman']):
                ghi        = np.array(weatherData['Rad1h'] * 0.2777778)                  # convert to Rad1h [kJ/m^2] to Wh/m^2
            if (model not in ['clearsky', 'clearsky_scaling', 'campbell_norman']):       # we don't need this for cloud models ...
                solar_position = self._location.get_solarposition(times       = weatherData.index,
                                                                  pressure    = weatherData[f['pressure']],
                                                                  temperature = weatherData[f['temp_air']] - 273.15)
                cosSZA         = np.cos(solar_position['zenith']*np.pi/180)
            if (model == 'disc' or model == 'dirint' or model == 'dirindex'):
                if (model == 'disc'):
                    disc = pvlib.irradiance.disc(ghi              = ghi,                 # returns dataframe with columns = ['dni', 'kt', 'airmass']
                                                 solar_zenith     = solar_position['zenith'],
                                                 datetime_or_doy  = weatherData.index,
                                                 pressure         = weatherData[f['pressure']])
                    dni  = np.array(disc['dni'])
                    kt   = np.array(disc['kt'])
                elif (model == 'dirint'):
                    dni  = pvlib.irradiance.dirint(ghi            = ghi,                 # returns array
                                                   solar_zenith   = solar_position['zenith'],
                                                   times          = weatherData.index,
                                                   temp_dew       = weatherData[f['temp_dew']] - 273.15)
                else:
                    
                    clearsky = self._location.get_clearsky(weatherData.index,            # calculate clearsky ghi, dni, dhi for times
                                                           model='ineichen')
                    dni  = pvlib.irradiance.dirindex(ghi          = ghi,                 # returns array
                                                     ghi_clearsky = clearsky['ghi'],
                                                     dni_clearsky = clearsky['dni'],
                                                     zenith       = solar_position['zenith'],
                                                     times        = weatherData.index,
                                                     pressure     = weatherData[f['pressure']],
                                                     temp_dew     = weatherData[f['temp_dew']] - 273.15)
                dhi = ghi - dni*cosSZA
            elif (model == 'erbs' or model == 'erbs_kt'):
                if (model == 'erbs'):
                    erbs = pvlib.irradiance.erbs(ghi             = ghi,                      # returns dataframe with columns ['dni', 'dhi', 'kt']
                                                 zenith          = solar_position['zenith'],
                                                 datetime_or_doy = weatherData.index)
                else:                                                                        # 'erbs_kt', needs modification in pvlib.irradiance.erbs
                    try:
                        erbs = pvlib.irradiance.erbs(ghi             = ghi,                  # returns dataframe with columns ['dni', 'dhi', 'kt']
                                                     zenith          = solar_position['zenith'],
                                                     datetime_or_doy = weatherData.index,
                                                     kt              = weatherData['RRad1']/100) # = kt, in range 0 .. 100
                    except Exception as e:
                        print("getIrradiance: ERROR --- erbs_kt needs modification to pvlib.irradiance.erbs()")
                        sys.exit(1)
                dni  = np.array(erbs['dni'])
                dhi  = np.array(erbs['dhi'])
                kt   = np.array(erbs['kt'])
            elif (model == 'clearsky'):
                clearsky_model  = self.config[self._cfg].get('clearsky_model', 'simplified_solis')
                self.irradiance = self._location.get_clearsky(weatherData.index,         # calculate clearsky ghi, dni, dhi for clearsky
                                                              model=clearsky_model)
            elif (model == 'clearsky_scaling' or model == 'campbell_norman'):
                if model == 'campbell_norman' and self._pvversion == '0.8.0':
                    raise Exception("ERROR --- cloud based irradiance model 'campbell_norman' only supported in pvlib 0.8.1 and higher")
                fcModel = ForecastModel('dummy', 'dummy', 'dummy')                       # only needed to call methods below
                fcModel.set_location(latitude=self._location.latitude, longitude=self._location.longitude, tz=self._location.tz)
                self.irradiance = fcModel.cloud_cover_to_irradiance(weatherData[f['clouds']], how = model)
            else:
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
            self.irradiance         = pd.concat([weatherData[f['temp_air']] - 273.15, weatherData[f['wind_speed']], self.irradiance], axis=1)
            self.irradiance.rename(columns={f['temp_air'] : 'temp_air', f['wind_speed'] : 'wind_speed'}, inplace=True)
            self._cloud_cover_param = f['clouds']
        except:
            pass

    def runModel(self, weather: Forecast, model, modelLst = 'all'):
        """Run one PV simulation model (named in self.pv_model, set in getIrradiance())
        Weather data is inherited from prior call to getIrradiance() call
        Populates self.sim_result      pandas dataframe with simulation results"""

        if modelLst is not None:
            if modelLst != 'all' and model != modelLst:                                   # we have an explict list of models to calculate
                modelLst = modelLst.replace(" ", "")
                models   = modelLst.split(",")
                if model not in models:                                                   # request was for something else ...
                    return None
        try:
            self.getIrradiance(weather, model)
            self._mc.run_model(self.irradiance)
            cols = ['ghi', 'dni', 'dhi']
            if 'kt' in self.irradiance: 
                cols.append('kt')
            if (self.pv_model == 'PVWatts'):
                self.DataTable = pd.concat([self._mc.dc, self._mc.ac, self.irradiance[cols]], axis=1)
            else:                                                                        # CEC
                self.DataTable = pd.concat([self._mc.dc.p_mp, self._mc.ac, self.irradiance[cols]], axis=1)
            m                  = self.irradiance_model
            if (m == 'clearsky_scaling' or m == 'campbell_norman'):
                m = m + '_' + self._cloud_cover_param
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
        if ('Rad1h' in weather.DataTable):                                               # ---- irrandiance based models
            dfList.append(self.runModel(weather, 'disc', modelLst))
            dfList.append(self.runModel(weather, 'dirint', modelLst))
            dfList.append(self.runModel(weather, 'dirindex', modelLst))
            dfList.append(self.runModel(weather, 'erbs', modelLst))
            if 'RRad1' in weather.DataTable and self._allow_experimental:
                dfList.append(self.runModel(weather, 'erbs_kt', modelLst))
        dfList.append(self.runModel(weather, 'clearsky_scaling', modelLst))              # ---- cloud based models
        if self._pvversion >= '0.8.1':                                                   # deprecated model 'liujordan' not implemented
            dfList.append(self.runModel(weather, 'campbell_norman', modelLst))
        dfList.append(self.runModel(weather, 'clearsky', modelLst))
        dfList.append(self._mc.solar_position.zenith)                                    # ---- add solar position
        self.DataTable = pd.concat(dfList, axis=1)
        drop           = []
        haveGHI        = False
        for col in self.DataTable:
            if 'ghi' in col and not (col.startswith('ghi_clearsky') or col.startswith('ghi_campbell')):
                if not haveGHI:
                    self.DataTable.rename(columns = {col: 'ghi'}, inplace=True)          # rename first GHI field as GHI, since this is input and hence same for all models
                    haveGHI = True
                else: drop.append(col)
            elif col == 'kt_erbs_kt': drop.append(col)                                   # redundant as kt is input to (experimental) erbs_kt
        if (len(drop) > 0): self.DataTable = self.DataTable.drop(drop, axis=1)

    def writeCSV(self, csvName):                                                         # write self.weatherData to .csv file
        """Store simulated PV power in .csv file"""

        path   = self.config[self._cfg].get('storePath')
        fName  = re.sub(r'\.kml$', '_sim.csv.gz', csvName)
        self.DataTable.to_csv(path + "/" + fName, compression='gzip')
        return()
