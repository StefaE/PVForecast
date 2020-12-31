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
from .dwdforecast import DWDForecast

class PVModel(Forecast):
    """Model PV output based on irradiance or cloud coverage data"""

    def __init__(self, config):
        """Initialize PVModel
        config      configparser object with section [PVSystem]"""

        super().__init__()
        self.config   = config
        self.config['DEFAULT']['NominalEfficiency'] =  '0.96'                            # nominal inverter efficiency, default of pvwatts model
        self.config['DEFAULT']['TemperatureCoeff']  = '-0.005'                           # temperature coefficient of module, default of pvwatts model
        self.config['DEFAULT']['TemperatureModel']  = 'open_rack_glass_glass'            # https://pvlib-python.readthedocs.io/en/stable/generated/pvlib.temperature.sapm_cell.html
        self.config['DEFAULT']['Altitude']          = '0'                                # default altitude sea level
        self.config['DEFAULT']['Model']             = 'CEC'                              # default PV modeling stratey
        self._weatherFields = {'dwd': { 'temp_air'   : 'TTT',                            # translation: DWD parameter names --> pvlib parameter names
                                        'wind_speed' : 'FF',                             #    Note that temp_air and temp_dew are in Celsius, TTT in Kelvin
                                        'pressure'   : 'PPPP',
                                        'temp_dew'   : 'Td',
                                        'clouds'     : 'N' },
                               'owm': { 'temp_air'   : 'temp',                           # translation: OWM parameter names --> pvlib parameter names
                                        'wind_speed' : 'wind_speed',                     #    Note that temp_air and temp_dew are in Celsius, TTT in Kelvin
                                        'pressure'   : 'pressure',
                                        'temp_dew'   : 'dew_point',
                                        'clouds'     : 'clouds' }}

        self._location = Location(latitude  = self.config['PVSystem'].getfloat('Latitude'),
                                  longitude = self.config['PVSystem'].getfloat('Longitude'), 
                                  altitude  = self.config['PVSystem'].getfloat('Altitude'),
                                  tz='UTC')                                              # let's stay in UTC for the entire time ...
        self._pvsystem          = None                                                   # PV system, once defined with init_CEC() or init_PVWatts()
        self._mc                = None                                                   # Model chain, once defined in init_CEC() or init_PVWatts()
        self._weather           = None                                                   # weather data used for getIrradiance() and runModel()
        self._cloud_cover_param = None                                                   # weather data parameter used for cloud coverage (see _weatherFields)
        self.irradiance_model   = None                                                   # model name if irradiance data calculated in getIrradiance()
        self.irradiance         = None                                                   # calculated irradiance data
        self.pv_model           = None                                                   # CEC or PVWatts once solar system is defined
        self.SQLTable           = 'pvsim'                                                # which SQL table name is this data stored to (see DBRepository.loadData())

    def init(self):
        if (self.config['PVSystem'].get('Model') == 'CEC'):
            self._init_CEC()
        else:
            self._init_PVWatts()

    def _init_CEC(self):
        """Configure PV system based on actual components available in pvlib CEC database"""

        try:
            moduleName     = self.config['PVSystem'].get('ModuleName')
            inverterName   = self.config['PVSystem'].get('InverterName')
            tempModel      = self.config['PVSystem'].get('TemperatureModel')
            self._pvsystem = PVSystem(surface_tilt                 = self.config['PVSystem'].getfloat('Tilt'),
                                      surface_azimuth              = self.config['PVSystem'].getfloat('Azimuth'),
                                      module_parameters            = pvlib.pvsystem.retrieve_sam('cecmod')[moduleName],
                                      inverter_parameters          = pvlib.pvsystem.retrieve_sam('cecinverter')[inverterName],
                                      strings_per_inverter         = self.config['PVSystem'].getint('NumStrings'),
                                      modules_per_string           = self.config['PVSystem'].getint('NumPanels'),
                                      temperature_model_parameters = TEMPERATURE_MODEL_PARAMETERS['sapm'][tempModel])
            self._mc       = ModelChain(self._pvsystem, self._location, aoi_model='physical', spectral_model='no_loss')
            self.pv_model  = 'CEC'
        except Exception as e:
            print("init_CEC: " + str(e))
            sys.exit(1)

    def _init_PVWatts(self):
        """Configure PV system using simplified PVWatts model"""

        try:
            pvwatts_module   = { 'pdc0'         : self.config['PVSystem'].getfloat('SystemPower'),
                                 'gamma_pdc'    : self.config['PVSystem'].getfloat('TemperatureCoeff') }
            pvwatts_inverter = { 'pdc0'         : self.config['PVSystem'].getfloat('InverterPower'), 
                                 'eta_inv_nom'  : self.config['PVSystem'].getfloat('NominalEfficiency') }
            pvwatts_losses   = { 'soiling'    : 0,   'shading': 0, 'snow':            0, 'mismatch': 0, 'wiring':       2, 
                                 'connections': 0.5, 'lid'    : 0, 'nameplate_rating':0, 'age':      0, 'availability': 0 }
            tempModel        = self.config.get('PVSystem', 'TemperatureModel')
            self._pvsystem   = PVSystem(surface_tilt                 = self.config['PVSystem'].getfloat('Tilt'),
                                        surface_azimuth              = self.config['PVSystem'].getfloat('Azimuth'),
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
                                    'liujordan', 'clearsky_scaling'          (cloud coverage to irradiance)
                                    'clearsky'                               (clear sky model)
        cloud_cover_param   name of cloud cover parameter in weather"""

        try:
            weatherData    = weather.DataTable                                           # extract weather data table from weather
            if ('Rad1h' not in weatherData and model not in ['clearsky', 'clearsky_scaling', 'liujordan']):
                raise Exception('ERROR --- weather does not include irradiation data, use cloud based models instead of = ' + model)
            elif (model not in ['clearsky', 'clearsky_scaling', 'liujordan']):
                ghi            = np.array(weatherData['Rad1h'] * 0.2777778)              # convert to Rad1h [kJ/m^2] to Wh/m^2
            f              = self._weatherFields[weather.SQLTable]                       # field mapping dicionary weather --> pvlib
            self.IssueTime = weather.IssueTime
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
            elif (model == 'erbs'):
                erbs = pvlib.irradiance.erbs(ghi             = ghi,                      # returns dataframe with columns ['dni', 'dhi', 'kt']
                                             zenith          = solar_position['zenith'],
                                             datetime_or_doy = weatherData.index)
                dni  = np.array(erbs['dni'])
                dhi  = np.array(erbs['dhi'])
                kt   = np.array(erbs['kt'])
            elif (model == 'clearsky'):
                self.irradiance = self._location.get_clearsky(weatherData.index,         # calculate clearsky ghi, dni, dhi for clearsky
                                                              model='ineichen')
            elif (model == 'clearsky_scaling' or model == 'liujordan'):
                fcModel = ForecastModel('dummy', 'dummy', 'dummy')                       # only needed to call methods below
                fcModel.set_location(latitude=self._location.latitude, longitude=self._location.longitude, tz=self._location.tz)
                self.irradiance = fcModel.cloud_cover_to_irradiance(weatherData[f['clouds']], model)
            else:
                raise Exception("ERROR --- incorrect irradiance model called: " + model)
        except Exception as e:
            print("getIrradiance: " + str(e))
            sys.exit(1)

        if (model != 'clearsky' and model != 'clearsky_scaling' and model != 'liujordan'):
            self.irradiance         = pd.DataFrame(data=[ghi, dni, dhi]).T
            self.irradiance.index   = weatherData.index
            self.irradiance.columns = ['ghi', 'dni', 'dhi']
        if (model == 'disc' or model == 'erbs'):
            self.irradiance['kt']   = kt
        self.irradiance_model       = model
        self._weather               = pd.concat([weatherData[f['temp_air']] - 273.15, weatherData[f['wind_speed']], self.irradiance], axis=1)
        self._weather.rename(columns={f['temp_air'] : 'temp_air', f['wind_speed'] : 'wind_speed'}, inplace=True)
        self._cloud_cover_param     = f['clouds']

    def runModel(self):
        """Run one PV simulation model (named in self.pv_model, set in getIrradiance())
        Weather data is inherited from prior call to getIrradiance() call
        Populates self.sim_result      pandas dataframe with simulation results"""

        try:
            if (self.irradiance is None):
                raise Exception("ERROR --- need call getIrradiance() prior to runModel()")
            self._mc.run_model(self._weather)
            if (self.pv_model == 'PVWatts'):
                self.DataTable     = pd.concat([self._mc.dc, self._mc.ac, self.irradiance], axis=1)
            else:                                                                        # CEC
                self.DataTable     = pd.concat([self._mc.dc.p_mp, self._mc.ac, self.irradiance], axis=1)
            m                       = self.irradiance_model
            if (m == 'clearsky_scaling' or m == 'liujordan'):
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

    def run_allModels(self, weather: Forecast):
        """Run all implemented models. Populates
        self.sim_result            pandas dataframe with all simulation results"""

        self.getIrradiance(weather, 'clearsky_scaling')
        clearsky_scaleing  = self.runModel()                                              # ---- cloud based models
        self.getIrradiance(weather, 'liujordan')
        liujordan          = self.runModel()
        self.getIrradiance(weather, 'clearsky')
        clearsky           = self.runModel()

        if ('Rad1h' in weather.DataTable):                                               # ---- irrandiance based models
            self.getIrradiance(weather, 'disc')
            disc           = self.runModel()
            self.getIrradiance(weather, 'dirint')
            dirint         = self.runModel()
            self.getIrradiance(weather, 'dirindex')
            dirindex       = self.runModel()
            self.getIrradiance(weather, 'erbs')
            erbs           = self.runModel()                                             #                                   0,  1,   2,   3,   4   5
            self.DataTable = pd.concat([disc,                                            # columns returned by runModel are dc, ac, ghi, dni, dhi, kt
                                        dirint.iloc[:, [0,1,3,4]], dirindex.iloc[:, [0,1,3,4]], erbs.iloc[:, [0,1,3,4,5]],
                                        clearsky_scaleing,
                                        liujordan, 
                                        clearsky, 
                                        self._mc.solar_position.zenith], axis=1)
            self.DataTable.rename(columns={'ghi_disc' : 'ghi'}, inplace=True)
        else:
            self.DataTable = pd.concat([clearsky_scaleing,
                                        liujordan, 
                                        clearsky, 
                                        self._mc.solar_position.zenith], axis=1)

    def writeCSV(self, kmlName):                                                         # write self.weatherData to .csv file
        """Store simulated PV power in .csv file"""

        path   = self.config['PVSystem'].get('storePath')
        fName  = re.sub(r'\.kml$', '_sim.csv.gz', kmlName)
        self.DataTable.to_csv(path + "/" + fName, compression='gzip')
        return()
