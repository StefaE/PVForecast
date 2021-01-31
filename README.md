# PVForecast
Rooftop PV production forecast
 
## Introduction
This project supports an extensive set of production forecasts for PV rooftop installations. Various weather data sources, PV modeling algorithms and storage methods for results can be used. 

The project has been developped on Python3 and runs on Raspberries and integrates with [solaranzeige](https://solaranzeige.de) - (see [Solaranzeige Integration](#solaranzeige-integration))

Generally, functionality is configured through a configuration file (default: `.\config.ini`, a different location can be provided with `-c` command line option)

Two main scripts are provided:
Script | Description
-------|------------
`PVForecasts.py` | enables all functionality described here
`SolCastLight.py` | can only use [Solcast](https://solcast.com/) forecasts but is significantly easier to install


## Main Functionality and Configuration
`.\config.ini` is a configuration file parsed with python's [configparser](https://docs.python.org/3/library/configparser.html). Most importantly:
* items can be promoted to the `[DEFAULT]` section if same `key = value` pair is used in multiple sections
* inline comments are configured to start with `#`
* multi-line values are not allowed
* outcommented `key = value` pairs show the respective default options, which could be changed as needed

The `config.ini` file provided with the distribution contains a few site specific values, which cannot be pre-configured. The are shown as `<xx>`.

### Forecast Sources
```
[Forecasts]                       # enable / disable certain forecasts
    Solcast           = 1         
    OWM               = 0         # OpenWeatherMap.org
    MOSMIX_L          = 0         # single station file, updated every 6h
    MOSMIX_S          = 0         # all stations,        updated hourly download
```

Forecast Sources can be enabled through 0 or 1. Any number of sources can be enabled simultaneously.

Source | Description
-------|------------
**Solcast** | Solar forecast by [Solcast](https://solcast.com/)
**OWM** | Weather forecast from [OpenWeatherMap.org](https://openweathermap.org/) with approx. 10 parameters
**MOSMIX** | provided by [Deutscher Wetterdienst](https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/met_verfahren_mosmix.html) (primarily of Germany). Two flavours exist: 
_MOSMIX_L_| single station forecast, updated four times per day and approx. 115 weather parameters
_MOSMIX_S_| comprehensive download file of all MOSMIX weather stations, updated hourly, containing approx. 40 weather parameters. **NOTE:** MOSMIX_S causes the download of a ~37MByte file every hour - ensure that you really want that and that you have enough internet bandwidth!

Depending on the data source, various forecast algorithms are available. The configuration happens in the respective sections described below.

### **Solcast** configuration
```
[SolCast]
    resource_id       = <resource_id_from_solcast.com>
    api_key           = <api_id_from_solcast.com>
    post              = 1         # enable posting and tuning
    # interval        = 60        # interval at which SolCast is read (during daylight only)
```

[Solcast](https://solcast.com/pricing/) allows for the free registration of a residental rooftop PV installation of up to 1MWp and allows for up to 20 API calls/day. The registration process provides a 12-digit _resource_id_ (`xxxx-xxxx-xxxx-xxxx`) and a 32 character API key.

To stay within the limits of 20 API calls/day, the API is only called with an `interval = 60` minutes between sunrise and sunset.

Solcast directly provides a PV forecast (in kW) for 30min intervals, with 10% and 90% confidence level. Hence, no further modelling is needed.

Solcast also allows to post PV performance data to [tune forecast](https://articles.solcast.com.au/en/articles/2366323-pv-tuning-technology) to eg. local shadows, etc. This can be enabled with `post = 1`. See [Solcast Tuning](#solcast-tuning) for how performacne data can be provided.

To calculate sunrise and sunset, we also need define the systems location. Since this data is also used for other models (below), it might be advisable to put these parameters into the `[Default]` section of the configuration file:
```
    Latitude          = 51.784635
    Longitude         =  6.104759
```

### **OWM** configuration
```
[OpenWeatherMap]
    api_key           = <api_id_from_openweathermap.org>
    Irradiance        = all       # irrandiance model (for OWM)
```

[OpenWeatherMap](https://openweathermap.org/price) offers free access to their API to regularly download weather forecasts. The registration process provides a 32 character API key.

The weather forecast consists of approx. 10 parameters, including cloud coverage, which can be modelled to a PV forecast (see [Forecast Models](#forecast-models))

### **MOSMIX** configuration
```
[DWD]
    DWD_URL_L         = https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/
    DWD_URL_S         = https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_S/all_stations/kml/
    DWDStation        = <station_number>    # Station number
    Irradiance        = all       # irradiance model (for MOSMIX)
    storeKMZ          = 0         # store downloaded .kmz files (.kml compressed as .zip)
    # keepKMZ_S       = 0         # keep MOSMIX_S original file after downloading     
```

Unlike modern APIs, _Deutscher Wetterdienst_ (DWD) allows only file download for what they call [MOSMIX data](https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/met_verfahren_mosmix.html). Hence, the software described here has to accomodate for the complications which come with such an out-dated approach.

Two download schemes (as described [above](#forecast-sources)) exist. Keys `DWD_URL_L` and `DWD_URL_S` provide the respective stems of download links. The station abreviation needs be taken from [their website](https://wettwarn.de/mosmix/mosmix.html)

`storeKMZ`: The files downloaded are named `*.kmz` which is inadequate in two ways: First, the files are simple `.zip` files (so, why are they not called that way?) and second, a `.zip` file is meant to contain multiple files, which clearly the `.kmz` files do not. Hence, with `storeKMZ = 1`, downloaded data is stored in the more adequate `.gz` format. For _MOSMIX_L_, the downloaded files for the selected station are stored. For _MOSMIX_S_, an extract for the selected station is stored in a self-contained compressed `.xml` file.

`keepKMZ_S`: in case of downloading the (huge) _MOSMIX_S_ file, they can be stored by enabling this option.

### Forecast models
Data from [OWM](#owm-configuration) and [MOSMIX](#mosmix-configuration) do not directly contain PV output power. This needs be modelled using functionality provided by [pvlib](https://pvlib-python.readthedocs.io/en/stable/). Multiple modelling approaches are supported, selected by the `Irradiance` parameter seen above. 

Essentially, the modelling consists of a two-step approach:
1. convert weather data to irradiation data (GHI, DNI, DHI)
2. convert such irradiation data into PV output power

#### Convert Weather Data to Irradation Data

Model | Input parameter | Applicable to | Comment
------|-----------------|---------------|--------
[disc](https://pvlib-python.readthedocs.io/en/stable/generated/pvlib.irradiance.disc.html)  | Rad1h (GHI)     | MOSMIX | not all stations have Rad1h, probably the 'standard' model
[dirint](https://pvlib-python.readthedocs.io/en/stable/generated/pvlib.irradiance.dirint.html) | Rad1h (GHI) | MOSMIX | not all stations have Rad1h
[dirindex](https://pvlib-python.readthedocs.io/en/stable/generated/pvlib.irradiance.dirindex.html) |Rad1h (GHI) | MOSMIX | not all stations have Rad1h, some numerical instabilities at very low values of GHI
[erbs](https://pvlib-python.readthedocs.io/en/stable/generated/pvlib.irradiance.erbs.html) | Rad1h (GHI) | MOSMIX | not all stations have Rad1h (*)
[campbell_norman](https://pvlib-python.readthedocs.io/en/stable/generated/pvlib.irradiance.campbell_norman.html) | cloud coverage | OWM, MOSMIX | cloud coverage is provided as parameter `clouds` and by MOSMIX parameter `N`
[clearsky_scaling](https://pvlib-python.readthedocs.io/en/stable/generated/pvlib.forecast.ForecastModel.cloud_cover_to_irradiance_clearsky_scaling.html?highlight=clearsky_scaling) | cloud coverage | OWM, MOSMIX | cloud coverage is provided as parameter `clouds` and by MOSMIX parameter `N`
[clearsky](https://pvlib-python.readthedocs.io/en/stable/generated/pvlib.location.Location.get_clearsky.html?highlight=get_clearsky#pvlib.location.Location.get_clearsky) | NA | OWM, MOSMIX | clear sky estimation of PV output power. Secondary weather parameters are considered. The default model used is `simplified_solis` (see [below](#convert-irradiation-data-to-pv-output-power)).
all | NA | NA | calculate all applicable models for provided weather data

Where needed, `DHI` is calculated from `GHI` and `DNI` using the fundamental equation `DNI = (GHI - DHI)/cos(Z)` where `Z` is the solar zenith angle (see eg. [Best Practices Handbook](https://www.nrel.gov/docs/fy15osti/63112.pdf))

Secondary weather parameters considered in above models include:

Parameter | OWM | MOSMIX
---------|-----|-------
temp_air | temp | TTT
wind_speed | wind_speed | FF
pressure  | pressure | PPPP
temp_dew | dew_point | Td

#### Convert Irradiation Data to PV Output Power
[pvlib](https://pvlib-python.readthedocs.io/en/stable/index.html) supports two modelling strategies for a PV system:
1. model system with actual component parameters based on a `CEC` database provided with pvlib
2. simplified `PVWatts` model

Both approaches are supported and selected based on `Model`
```
[PVSystem]
    # Model            = CEC      # modeling strategy for PV: 'CEC' or 'PVWatts' 
    # TemperatureModel = open_rack_glass_glass
    # clearsky_model   = simplified_solis
    
    # --------------------------- physical definition of PV System, using CEC database
    # based on .csv files at ~/.local/lib/python3.8/site-packages/pvlib/data, special characters to be replaced by '_'
    ModuleName        = LG_Electronics_Inc__LG325N1W_V5
    InverterName      = SMA_America__SB10000TL_US__240V_
    NumStrings        =   2       # number of strings 
    NumPanels         =  15       # number of panels per string
    
    # --------------------------- PVWatts definition
    InverterPower     = 10000     # name-plate inverter max. power
    NominalEfficiency = 0.965     # nominal European inverter efficiency
    SystemPower       =  9750     # system power [Wp]
    TemperatureCoeff  = -0.0036   # temperature coefficient (efficiency loss per 1C)
```

If the (preferred) `CEC` approach is used, the selected model should at a minimum match the nameplate power of the installed panels (eg. 325Wp). The selected inverter is uncritical as long as the nameplate power is same or higher as installed inverter (eg. 10kW) - the modeling of inverters is relatively poor in pvlib, considering only a _NominalEfficency_.

The `PVWatts` model considers the following inefficiencies (which is less than [PVWatts defaults](https://pvlib-python.readthedocs.io/en/stable/generated/pvlib.pvsystem.pvwatts_losses.html?highlight=pvwatts_losses#pvlib.pvsystem.pvwatts_losses), which are meant to model monthly or annual output):
```
    pvwatts_losses   = { 'soiling'          : 0,   
                         'shading'          : 0, 
                         'snow'             : 0, 
                         'mismatch'         : 0, 
                         'wiring'           : 2, 
                         'connections'      : 0.5, 
                         'lid'              : 0, 
                         'nameplate_rating' : 0, 
                         'age'              : 0, 
                         'availability'     : 0 }
```

`pvlib` models panel temperature (and related efficiency loss) based on `TemperatureModel` and weather parameter `temp_air`.

`clearsky_model` is used for irradiation model `clearsky`. `ineichen` and `simplified_solis` are supported, `haurwitz` is not.

Both models also need basic parameters of the system location and orientation:
```
    Latitude          = 51.784635
    Longitude         =  6.104759
    Altitude          = 74        # altitude of system (above sea level)
    Tilt              =  30
    Azimuth           = 127       # 270=West, 180=South, 90=East
```
Since latitude and longitude parameters are also needed by [Solcast](#solcast-configuration) to calculate sunrise and sunset, it is efficient to put above parameters into the `[Default]` section of the configuration file.

### Data Storage
Forecasting PV output power would be pointless, if the resulting data wouldn't be stored anyway. The application supports two main storage models:
1. SQLite (file based relational database)
2. Influx

The following configuration parameters control what is stored where and can be configured separately in sections `[SolCast], [OpenWeatherMap], [DWD]` or commonly in section `[Default]`

Parameter | Function 
----------|----------
storeDB   | enable SQLite storage 
storePath | storage location of SQlite database 
storeInflux | enable Influx storage 

#### SQLite Storage
```
[DBRepo]
    dbName  = pvforecasts.db      # SQLite database name (at 'storePath')
```
An SQLite database is dynamically created with above defined name at `storePath`. It will contain a (subset of) the following tables, depending on what models have been calculated:
Table | Content
------|--------
dwd   | all weather parameters from MOSMIX_L
dwd_s | all weather parameters from MOSMIX_S
pvsystem | PV model output parameters (GHI, DHI, DNI, DC power, AC power, solar zenith angle) for all calculated [irradance models](#convert-weather-data-to-irradation-data)
pvsystem_s | same for output parameters based on `dwd_s`
owm | OpenWeatherData weather fields and PV modeling output
solcast | PV output power estimates

All tables contain `IssueTime` (when forecast was issued) and `PeriodEnd` (end time of forecast period). Date from previous `IssueTime` are not deleted to allow analysis of accuracy of forecasts over different forecast horizons.

All times are in UTC.

#### Influx Storage
```
[Influx]
    host              = <your_hostname>         # can be localhost
    # port            = 8086
    database          = <your_influx_db_name>   
    power_field       = PV.Gesamtleistung
```

This will create the following _measurements_ (akin tables) in the defined Influx database:
Table | Content
------|--------
solcast | power estimates: `pv_stimate`, `pv_estimate10`, `pv_estimate90`
owm     | DC power estimates from OpenWeatherMap, named `dc_<model>`
pvsystem | DC power estimates from MOSMIX_L, named `dc_<model>`
pvsystem_s | DC power estimates from MOSMIX_S, named `dc_<model>`
forecast_log | log table on data downloads from [forecast sources](#forecast-sources)
where `<model>` refers to one of the [irradiance](#convert-weather-data-to-irradation-data) models calculated

`power_field` will be discussed in [Solcast Tuning](#solcast-tuning)

### Solaranzeige Integration
This application is designed to run seamlessly alongside [solaranzeige](https://solaranzeige.de). Hence, if installed on the same host, the `[Influx]` configuration section discussed in previous section may very well look like this:
```
[Influx]
    host              = localhost
    database          = solaranzeige   
    power_field       = PV.Gesamtleistung
```
This will add the discussed _measurements_ to the `solaranzeige` database and make them immediatly available for display in Grafana.

### Solcast Tuning

## Installation
 
## Disclaimer
The software pulls weather data from various weather sources. It is the users responsability to adhere to the use conditions of these sources. 

The author cannot provide any warranty concerning the availability, accessability or correctness of such weather data and/or the correct computation of derieved data for any specific use case or purpose.

Further warranty limitations are implied by the license

## License
Distributed under the terms of the GNU General Public License v3.
