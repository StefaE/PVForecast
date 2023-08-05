---
title: Users Guide
layout: template
order: 4
filename: README
---

# PVForecast User's Guide
A high level introduction to the project is given [here](https://stefae.github.io/PVForecast/). This _README_ file provides a full description of installation and configuration
 
## Introduction
An extensive set of forecasts relevant to PV rooftop installations is supported:
* production forecasts based on a number of providers (many users may focus on [SolCast](https://solcast.com/free-rooftop-solar-forecasting) for easy installation and excellent forecast quality)
* <span style="color:#00B0F0"><b>New in v2.10:</b></span> (for EU only)
	+ forecast of CO2 intensity of grid electricity consumed ([CO2signal](#co2signal-configuration) shows actual data for many areas of the world)
	+ auction prices of grid electricity
* v2.11, v2.11.01: bug fixes

<span style="color:red"><b>Upgrade Notice:</b></span> incompatible changes - see [Version History](#version-history) for details
* v2.11 sets default `apiCalls = 10` for [SolCast](#solcast-configuration) - legacy users with more credits need set `apiCalls` explicitly.
* v2.10 requires pvlib v0.9.0 or higher (for **full version only**); small changes to `config.ini` keys and defaults, `SolCastLight` is deprecated (but still works)
* v2.00 contains some incompatible changes (for the **full version** only) - . For users of the **light version**, there is no incentive to upgrade from v1.02/v1.03.

-------------
## Table of Content
  - [Installation](#installation)
    - [Setup](#setup)
    - [Running the Script](#running-the-script)
  - [Configuration](#configuration)
    - [Sections](#sections)
    - [Default Section](#default-section)
  - [Configuring Data Sources](#configuring-data-sources)
    - [Forecast Sources](#forecast-sources)
    - [SolCast Configuration](#solcast-configuration)
    - [VisualCrossing Configuration](#visualcrossing-configuration)
    - [DWD configuration](#dwd-configuration)
    - [OpenWeatherMap Configuration](#openweathermap-configuration)
    - [Entso-E Configuration <span style="color:#00B0F0"><b>new</b></span>](#entso-e-configuration)
    - [CO2signal Configuration <span style="color:#00B0F0"><b>new</b></span>](#co2signal-configuration)
    - [FileInput Configuration](#fileinput-configuration)
  - [Configuring PV Output Power Forecast Modelling](#configuring-pv-output-power-forecast-modelling)
    - [Convert Weather Data to Irradiation Data](#convert-weather-data-to-irradiation-data)
    - [Convert Irradiation Data to PV Output Power](#convert-irradiation-data-to-pv-output-power)
      - [PVWatts Modelling](#pvwatts-modelling)
      - [CEC Modelling](#cec-modelling)
    - [Split Array System Configuration](#split-array-system-configuration)
  - [Configuring Data Storage](#configuring-data-storage)
    - [SQLite Storage](#sqlite-storage)
    - [Influx Storage](#influx-storage)
      - [Influx v2.x Storage](#influx-v2x-storage)
      - [Influx v1.x Storage](#influx-v1x-storage)
    - [.csv File Storage](#csv-file-storage)
  - [Version History](#version-history)
    - [Deprecations](#deprecations)
  - [Acknowlegements](#acknowlegements)
  - [License and Disclaimer](#license-and-disclaimer)

-------------

## Installation

### Setup

Installation mainly ensures that all necessary python packages are available. We assume a Raspberry host here - although the instructions are probably quite generic. The scrip requires Python 3.8 or newer.

Required packages are described in [requirements.txt](https://github.com/StefaE/PVForecast/blob/main/requirements.txt). These packages can be installed manually (with `python -m pip install package)` or with `python -m pip install -r requirements.txt`. Referring to this file, which contains comments:
* the first group of packages is required mandatorily
* the `Influx` related packages are required if [Data Storage](#configuring-data-storage) to `Influx` (v1.8 or v2.x) is desired.
* the last group of packages are the most difficult to install, but only required if corresponding functionality is needed:
  + `pvlib` models [PV output power](#configuring-pv-output-power-forecast-modelling) and used for  [Forecast Sources](#forecast-sources) providing radiation data (`VisualCrossing`, `MOSMIX`, `OWM`) but **not** for `SolCast`
  + `entso-py` is required only for [CO2 intensity forecast](#entso-e-configuration) (and easy to install)
  
[Influx](https://www.influxdata.com/products/influxdb/) must be installed separately. `SQLite` is supported natively by Python. However, an [SQLite browser](https://sqlitebrowser.org/) maybe useful.

Additional help for installation is in the [project wiki](https://github.com/StefaE/PVForecast/wiki).

### Running the Script

After downloading the script from Github, into a directory of your choosing (eg. `\home\pi\PV`), you should have these files (and some more):
```
./PVForecasts.py
./config.ini
  |- ./PVForecast/*py
  |- ./docs
  |- ./emissionFactors
  +- ./data
./LICENSE
```

* update the config file (`config.ini`)
* try it out ...: `python PVForecast.py`
* install it in `cron`, so that it runs in regular time intervals

A typical `crontab` entry can look like so (assuming you have downloaded into `\home\pi\PV`):
```
*/15 * * * * cd /home/pi/PV && /usr/bin/python3 PVForecast.py >> /home/pi/PV/data/err.txt 2>&1
```
which would run the script every 15min 
+ 15min interval is recommended due to the API call management provided for [SolCast](#solcast-configuration). For other data sources, the script handles larger calling intervals internally.
+ when using `solcast_light_config.ini` it is recommended to rename this file to `config.ini`. Then we don't need the `-c` argument

A great explanation of `cron` is from [crontab guru](https://crontab.guru/examples.html). Crontab entries are made with `crontab -e` and checked with `crontab -l`.

**Note:** The script doesn't do much in terms of housekeeping (eg., limit size of SQLite database or `err.txt` file used above to redirect error messages).

## Configuration
`.\config.ini` is a configuration file parsed with python's [configparser](https://docs.python.org/3/library/configparser.html). It consists of `Sections` and `key = value` pairs. Most importantly:
* inline comments are configured to start with `#`
* multi-line values are not allowed
* out-commented `key = value` pairs in the provided `config.ini` template show the respective default options
* the [template config.ini](https://github.com/StefaE/PVForecast/blob/main/config.ini) contains many useful comments, so should be read alongside this description
* a few site specific values, which cannot be pre-configured. The are shown as `<xx>`.

### Sections

Section | Description |
--------|-------------|
`[Default]`	| If a key-value pair is not found in a specific section, the corresponding value in the default section is used. |
`[Forecasts]` | Forecasts to be run. If this section is missing, all forecasts for which a specific section exists is run |
Forecast configs | Each forecast source has its own section: _SolCast, VisualCrossing, DWD, OpenWeatherMap, Entso-E, CO2signal, FileInput_ |
`[PVSystem]` | describes the PV system (for forecast sources which require modelling: _VisualCrossing, DVD, OpenWeatherMap_. For [split-array configurations](#split-array-system-configuration), additional sections can be created |
`[DBRepo]` | configuration of [_SQLite_ storage](#sqlite-storage)
`Influx]`  | configuration of [_Influx_ storage](#influx-storage)

### Default Section

The following parameters are used by many forecast sources and hence typically placed into the `[Default]` section.

```
[DEFAULT]
    # ----------------------------------------------------- Storage locations
    storePath         = ./data/   # storage location for files (.csv, .kml, ..._ and SQLite database)
    # following parameters could be overwritten for individual forecast providers
    storeDB           = 0         # store to SQLite database (see [DBRepo] for name)
    storeCSV          = 0         # store .csv files (mainly for debugging)
    storeInflux       = 1         # store DC power output estimates in Influx (see [Influx] for name)
    # dropWeather     = 1         # drop weather parameters irrelevant for PV forecasting for 'storeDB', 'storeCSV'
    # force           = 0         # force downloading of new data

    # ----------------------------------------------------- Location of PV system
    Latitude          = <latitude_of_your_system>
    Longitude         = <longitude_of_your_system>
    # Altitude        = 0            # altitude of system (meters above sea level)
```

Parameters `storeXX` all default to `0` (False), but at least one must be set to `1`.
For `dropWeather`, see [SQLite Storage](#sqlite-storage)
`force` overwrites time-based blocking of downloading new data, if, for a data source, last data was downloaded not too long ago. Blocking time intervals are different per data source.

## Configuring Data Sources

### Forecast Sources

Source | Description | Look-ahead |
-------|-------------|------------|
[Solcast](#solcast-configuration) | Solar forecast by [Solcast](https://solcast.com/) | Default 7 days |
[VisualCrossing](#visualcrossing-configuration) | Weather and solar forecast from [VisualCrossing](https://www.visualcrossing.com/) | 15 days |
[DWD](#dwd-configuration) | provided by [Deutscher Wetterdienst](https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/met_verfahren_mosmix.html) (primarily for Germany). Two flavours exist: | 10 days |
_MOSMIX_L_ | single station forecast | 
_MOSMIX_S_ | all weather stations | 
[OpenWeatherMap](#openweathermap-configuration) | Weather forecast from [OpenWeatherMap.org](https://openweathermap.org/) with approx. 10 parameters. Cloud coverage is used for PV output power forecast | 2 days |
[Entso-E](#entso-e-configuration) | CO2 intensity for grid power, Electricity auction prices (EU only, based on data from [Entsoe Transparency Platform](https://transparency.entsoe.eu/)) | ~1 day |
[CO2signal](#co2signal-configuration) | actual CO2 intensity for grid power, provided by [Electricity Maps](https://www.electricitymaps.com/) | na |

_VisualCrossing, DWD_ and _OpenWeatherMap_ need modeling as described [below](#configuring-pv-output-power-forecast-modelling)

Depending on the data source, various forecast algorithms are available. The configuration happens in the respective sections described below.

### SolCast Configuration
```
[SolCast]
    resource_id       = <resource_id_from_solcast.com>
    # resource_id_2   = <second_resource_id_from_solcast.com>
    api_key           = <api_id_from_solcast.com>
    # interval        =  0        # interval at which SolCast is read (during daylight only)
    # hours           = 168       # forecast period defaults to 7 days, up to 14 days (336h)
    # apiCalls        =  10       # number of API calls supported by SolCast (new default in v2.11.00)  
```

[Solcast](https://solcast.com/free-rooftop-solar-forecasting) allows for the free registration of a residential rooftop PV installation of up to 1MWp and allows for up to 10 API calls/day (legacy users may benefit from more credits and can set their entitlement with `apiCalls`). The registration process provides a 12-digit _resource_id_ (`xxxx-xxxx-xxxx-xxxx`) and a 32 character API key. _SolCast_ also supports [dual array systems](https://articles.solcast.com.au/en/articles/2887438-how-do-i-create-a-multiple-azimuth-rooftop-solar-site) (eg., east/west) through a second `resource_id_2`.

_SolCast_ directly provides a PV forecasts (in kW) for 30min intervals, with 10% and 90% confidence level. Hence, no further modelling is needed. Forecasts are [updated every 15min](https://solcast.com/live-and-forecast) (for Eurasia), but it is recommended to call _SolCast_ no more than every 30min.

To stay within the limits of `apiCalls` per day, the script calls the API only between sunrise and sunset, except in the `24h` configuration below. It can further manage the calling interval to the API automatically or explicitly through the value assigned to `interval`:

value | meaning
------|---------
0     | **Default**: call API every 15min (single array) or 30min (dual-array). To not exceed maximum API calls, extend interval to 30min (60min) after sunrise and before sunset on long days. Hence, this provides most accurate (short-term) forecasts during mid-day.
early | same as `0`, but all interval extensions are done before sunset only. Hence, this provides most accurate forecasts in the morning (this is not useful for `apiCalls < 25`)
late  | same as `0`, but all interval extensions are done after sunrise only. Hence, this provides most accurate forecasts in the afternoon (this is not useful for `apiCalls < 25`)
24h   | downloads over the full day, but intervals are longer than in the previous configuration
number | a positive number (eg. 15, 30, 60, ...) ensures that the API is not called more frequently than the stated number of minutes. It is the users responsability to stay within the limits of `apiCalls` supported by _SolCast_

There is obviously an interaction between the `interval` settings and the `crontab` entry used to run the script (see [above](#running-the-script)). It is suggested to configure `crontab` to run the script every 30min (for `apiCalls >=25`, every 15min is possible). The interested user can use the script `./debug/solcast_timeInterval.py` to learn how download intervals are calculated - self-study is required).

Parameters `Latitude` and `Longitude` are only used to calculate daylight time. Defaults are for Frankfurt, Germany. (The _SolCast_ service has it's own location information, associated with the `api_key`.)

`hours` defines the forecast period and defaults to 168h, but can be extended up to 14 days (336h)

### VisualCrossing Configuration
```
[VisualCrossing]
    api_key           = <api_id_from_visualcrossing.com>
    # Irradiance      = disc        # default irradiation model
```
[VisualCrossing](https://www.visualcrossing.com/weather-data-editions) offers free access to their API to regularly download weather forecasts. The registration process provides a 25 character API key.

The [Weather Timeline API](https://www.visualcrossing.com/resources/documentation/weather-api/timeline-weather-api/) provides a 15-day forecast of approx. 18 parameters, including _solarradiation_ (or GHI). This can be converted to a PV output power forecast (see [Forecast Models](#configuring-pv-output-power-forecast-modelling)). The modelling strategy is controlled with the `Irradiance` parameter as described below.

`dropWeather`, `Latitude` and `Longitude` are typically provided in `[Default]` section.

### DWD configuration

[Deutscher Wetterdienst (DWD)](https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/met_verfahren_mosmix.html) supports two (file based) interfaces (without the requirement of authentication):
* `MOSMIX_L`: single weather station forecast, updated four times per day and approx. 115 weather parameters
* `MOSMIX_S`: all MOSMIX weather stations, updated hourly, containing approx. 40 weather parameters

Although both interfaces are supported, it is strongly suggested to use `MOSMIX_L`, since `MOSMIX_S` causes a download volume of ~1GByte/day without improving the forecast quality (despite the shorter update interval). `MOSMIX_S` can only be called from the [Forecast](#sections) section.

```
[DWD]
    DWDStation        = <station_number>    # Station number
    # DWD_URL_L       = https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/
    # DWD_URL_S       = https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_S/all_stations/kml/
    # Irradiance      = disc    # default irradiation model
    # storeKMZ        = 0       # store downloaded .kmz files (.kml compressed as .zip)
    # keepKMZ_S       = 0       # keep MOSMIX_S original file after downloading - note that these are many big files!
```

Valid `DWDStation` values are defined on the [MOSMIX website](https://wettwarn.de/mosmix/mosmix.html)

`storeKMZ`: The files downloaded are named `*.kmz` which is inadequate in two ways: First, the files are simple `.zip` files (so, why are they not called that way?) and second, a `.zip` file is meant to contain multiple files, which clearly the `.kmz` files never do. Hence, with `storeKMZ = 1`, downloaded data is stored in the more adequate `.gz` format. For _MOSMIX_L_, the downloaded files for the selected station are stored. For _MOSMIX_S_, an extract for the selected station is stored in a self-contained compressed `.xml` file. That format is very similar to _MOSMIX_L_ files.

`keepKMZ_S`: in case of downloading the (huge) _MOSMIX_S_ file, they can be stored by enabling this option. 

The modelling strategy used to convert weather data to irradiance is controlled with the `Irradiance` parameter as described in the next section. Not all MOSMIX stations support irradiance data (inconveniently labeled `Rad1h`). If the chosen station does not have it, irradiance based models won't work, but cloud-based models still do.

`dropWeather` is typically provided in `[Default]` section.

### OpenWeatherMap Configuration

```
[OpenWeatherMap]
    api_key           = <api_id_from_openweathermap.org>
    # Irradiance      = clearsky_scaling    # default irradiation model
```

[OpenWeatherMap](https://openweathermap.org/price) offers free access to their API to regularly download weather forecasts. The registration process provides a 32 character API key.

The weather forecast consists of approx. 10 parameters, including cloud coverage, which can be modelled to a PV forecast (see [Forecast Models](#configuring-pv-output-power-forecast-modelling)). The modelling strategy is controlled with the `Irradiance` parameter as described below.

`dropWeather`, `Latitude` and `Longitude` are typically provided in `[Default]` section.

### Entso-E Configuration

<span style="color:#00B0F0"><b>new</b></span> - this works only for EU area. A detained introduction to the ideas behind this is given on a separate [CO2 Intensity](CO2Intensity) page

[Entso-E](https://www.entsoe.eu/), the _European Network of Transmission System Operators for Electricity_, operates the [EU Transparency Platform](https://transparency.entsoe.eu/dashboard/show) with the goal to promote transparency goals to stakeholders.

```
[Entso-E]
    api_key             = <api_from_Entso-E>
    zones               = DE, DE_AMPRION                       # comma separated list of zones to be analyzed
    # resolution        = 60T                                  # some countries offer bidding prices for different time intervals, typically 15T and 60T
    # verbose           = 0                                    # verbosity level: 0=default, 1=basic, 2=max; forced =2 if start/end date are given
    # keepRaw           = 0                                    # default 0, together with start/end can be used to dump Entso-E data to .csv
    # start             = 2023-01-01T23:00Z                    # - see User's Guid
    # end               = 2023-02-18T23:00Z                    # -
    # loop              = 0                                    # -
```

An `api_key` can be requested as described in the [User's Guide, chapter 2](https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html#_authentication_and_authorisation).

Data can then be downloaded for a comma separated list of `zones`. Depending on selected zone(s), different data is available and calculated. A list of zones - and available data per zone - is [here](https://github.com/StefaE/PVForecast/docs/EntsoE_Zones.pdf). For more details, refer to the [CO2 Intensity](CO2Intensity) page, where also the other parameters are explained.

To get accurate data, a rolling linear correlation fit between forecasts and actuals is used. Due to this, the system needs to run for a couple of days before accurate forecasts are achieved.

### CO2signal Configuration

<span style="color:#00B0F0"><b>new</b></span> - A detained introduction to the ideas behind this is given on a separate [CO2 Intensity](CO2Intensity) page

```
[CO2signal]
    api_key             = <api_from_www.co2signal.com>
    zones               = DE      # comma separated list of zones to be downloaded
```

[ElectricityMaps](https://www.electricitymaps.com/) generate CO2 intensity data for many regions of the world. A free API is available at [CO2signal](https://www.co2signal.com/), which provides hourly data of the CO2 footprint of grid electricity (there is no forecast available), where a free `api_key` can be registered.

`zones` is a comma-separated list of zones to be downloaded, from a list of [supported zones](https://api.electricitymap.org/v3/zones).

### FileInput Configuration

```
[FileInput]
    ...
```
This forecast source is for mainly for debugging purposes and allows to read `.kmz` or `.csv` files with weather data. Refer to comments in sample `config.ini` file and source code `ForecastManager.processFileInput` for further guidance.

## Configuring PV Output Power Forecast Modelling
<a href="https://pvlib-python.readthedocs.io/en/stable/">
   <img style="margin-left:0" src="pictures/pvlib_powered_logo_horiz.png">
</a>

Data from all PV output power related data sources (except [SolCast](#solcast-configuration)) do not directly contain PV output power. This needs be modelled using functionality provided by [pvlib](https://pvlib-python.readthedocs.io/en/stable/). 

Essentially, the modelling consists of a two-step approach:
1. convert weather data to irradiation data (_GHI, DNI, DHI_). Multiple conversion strategies are available and controlled with the `Irradiance` parameter in the config section for `[VisualCrossing]`, `[DWD]` and `[OpenWeatherMap]` respectively.

2. convert such irradiation data into PV output power. This is controlled in the config section `[PVSystem]`

### Convert Weather Data to Irradiation Data

Model | Input parameter | Applicable to | Comment
------|-----------------|---------------|--------
[disc](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.irradiance.disc.html)  | `GHI`     | MOSMIX (*), VisualCrossing | default if GHI available
[dirint](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.irradiance.dirint.html) | `GHI` | MOSMIX (*), VisualCrossing | 
[dirindex](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.irradiance.dirindex.html) | `GHI` | MOSMIX (*), VisualCrossing | some numerical instabilities at very low values of GHI
[erbs](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.irradiance.erbs.html) | `GHI` | MOSMIX (*), VisualCrossing | 
[campbell_norman](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.irradiance.campbell_norman.html) | `clouds` | OWM, MOSMIX | 
[clearsky_scaling](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.forecast.ForecastModel.cloud_cover_to_irradiance_clearsky_scaling.html) | `clouds` | OWM, MOSMIX | default if GHI not available, 
[clearsky](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.location.Location.get_clearsky.html) | NA | all (except SolCast), output agnostic to weather forecast | clear sky estimation of PV output power; uses `simplified_solis`
all | NA | NA | calculate all applicable models for provided weather data

(*) not all MOSMIX stations provide GHI data

Where needed, `DHI` is calculated from `GHI` and `DNI` using the fundamental equation `DNI = (GHI - DHI)/cos(Z)` where `Z` is the solar zenith angle (see eg. [Best Practices Handbook](https://www.nrel.gov/docs/fy15osti/63112.pdf)). Weather parameters considered in above models include:

Parameter | VisualCrossing | MOSMIX | OpenWeatherMap | unit
---------|-----------------|--------|-----|------
ghi      | solarradiation | Rad1h | - | W/m<sup>2</sup>
temp_air | temp | TTT | temp | K
temp_dew | dew | Td | dew_point | K
wind_speed | windspeed | FF | wind_speed | m/s
pressure  | pressure | PPPP | pressure | Pa
clouds   | cloudcover | Neff | clouds | 0 .. 100

Where needed, unit conversion and parameter renaming is performed. `Parameter` correspond to same-named `pvlib` parameters and are stored in the [SQLite Storage](#sqlite-storage), if enabled.

MOSMIX `Rad1h` is (according to DWD customer service) the integrated radiation over the last hour prior to the forecast time stamp. For VisualCrossing, the [documentation](https://www.visualcrossing.com/resources/documentation/weather-api/timeline-weather-api/) states that `solarradiation` is the power _at the instantaneous moment of the forecast_. Hence, it probably best reflects the average radiation for a period beginning 30min before and ending 30min after the forecast timestamp. To account for this, the forecast time stamp `period_end` is corrected by +30min (which is then slightly misleading for the secondary weather parameters reported) once it gets [written out](#configuring-data-storage)

### Convert Irradiation Data to PV Output Power
In this section, we first describe how to model a single array PV System. The software also supports the configuration of split array systems. The necessary extensions are described in the next section.

[pvlib](https://pvlib-python.readthedocs.io/en/stable/index.html) supports two modelling strategies for a PV system:
* simplified `PVWatts` model
* model system with actual component parameters based on a `CEC` database provided with pvlib

Both approaches are supported and selected based on `Model`, but `PVWatts` is simpler to configure:

#### PVWatts Modelling
```
[PVSystem]
    # Model            = PVWatts  # modeling strategy for PV: 'CEC' or 'PVWatts' 
    # TemperatureModel = open_rack_glass_glass
    # clearsky_model   = simplified_solis
    
    # --------------------------- PVWatts definition
    InverterPower     = 10000     # name-plate inverter max. power
    NominalEfficiency = 0.965     # nominal European inverter efficiency
    SystemPower       =  9750     # system power [Wp]
    TemperatureCoeff  = -0.0036   # temperature coefficient (efficiency loss per 1C)
```

The `PVWatts` model considers considerably less inefficiencies (~2.5%) than [PVWatts defaults](https://pvlib-python.readthedocs.io/en/stable/reference/pv_modeling/generated/pvlib.pvsystem.pvwatts_losses.html) (~14%):

#### CEC Modelling

To use actual PV system component data, the `CEC` model must be used instead:

```
[PVSystem]
    Model            = CEC        # modeling strategy for PV: 'CEC' or 'PVWatts' 
    # TemperatureModel = open_rack_glass_glass
    # clearsky_model   = simplified_solis
    
    # --------------------------- physical definition of PV System, using CEC database
    # based on .csv files at .../pvlib/data, special characters to be replaced by '_'
    ModuleName        = LG_Electronics_Inc__LG325N1W_V5
    InverterName      = SMA_America__SB10000TL_US__240V_
    NumStrings        =   2       # number of strings 
    NumPanels         =  15       # number of panels per string
```

The location of the `pvlib` library can be determined with `python -m pip show pvlib`. The two `.csv` files `sam-library-cec-inverters-2019-03-05.csv` and `sam-library-cec-modules-2019-03-05.csv` list inverters and modules respectively. The first column contain the names of supported inverters and modules. Special characters and blanks need replaced with `_` in the config file. Hence, eg. `SMA America: SB10000TL-US [240V]` becomes `SMA_America__SB10000TL_US__240V_`

The selected model should at a minimum match the nameplate power of the installed panels (eg. 325Wp). The selected inverter is uncritical as long as the nameplate power is same or higher as installed inverter (eg. 10kW) - the modeling of inverters is relatively poor in pvlib, considering only a _NominalEfficency_.

`pvlib` models panel temperature (and related efficiency loss) based on `TemperatureModel` and weather parameter `temp_air`. `clearsky_model` is used for irradiation model `clearsky`. `ineichen` and `simplified_solis` are supported, `haurwitz` is not.

Both models also need basic parameters of the system location and orientation:
```
    # Latitude, Longitude, Altitude required, but typically taken from [Default] section
    Tilt              =  30
    Azimuth           = 127       # 270=West, 180=South, 90=East
```

### Split Array System Configuration
The above allows the definition of a _single array_ PV system. Split array systems (eg. with a west and east looking set of panels) can be configured as follows:
```
[PVSystem]
    # define one array as explained in previous section
    # additionally, following two parameters are supported:
    suffix     = West             # value = name of this array; default '1'
    storage    = both             # legal values: individual, both, sum (default)

[PVSystem_East]
    # define settings applicable to this array

[PVSystem_South]
    # define settings applicable to this array
```
There is no limit to the number of splits that can be defined.

Names of the sub-arrays are arbitrary - anything after the `_` serves as a suffix (here eg. `East`, `South`). Since the first section does not contain such a name (the section is strictly named `[PVSystem]`) a suffix can be provided separately (eg. `West`)

The secondary arrays (`[PVSystem_East]`, `[PVSystem_South]`, ...) inherit all settings from `[PVSystem]` except those which are explicitly overwritten. Typically, one wants to overwrite at least `Azimuth` and `Tilt`, likely also `NumStrings`, `NumPanels` and possibly panel types.

PV output is calculated for each sub-array and creates parameters `dc_<irradiation_model>_<suffix>` and `ac_<irradiation_model>_<suffix>`. Parameters are added as columns to the same table a single-array PV system would have created. The parameter `storage` controls what is handed to the [data storage](#configuring-data-storage) module. Valid values are:

Value | Function
------|---------
sum | **default**: only sum of all sub-arrays is stored (as `dc_/ac_<irradiation_model>`)
individual | only the individual sub-array results are stored, but sum is not calculated
both | individual results and sum are stored

## Configuring Data Storage
Forecasting PV output power would be pointless, if the resulting data wouldn't be stored anywhere. The application supports three storage models:
1. SQLite (file based relational database)
2. Influx
3. csv files

The following configuration parameters control what is stored where and can be configured separately for each forecast provider or, more commonly, in section `[Default]` (0 = disable, 1 = enable)

Parameter | Function 
----------|----------
storeDB   | enable SQLite storage 
storeInflux | enable Influx storage 
storeCSV  | enable CSV file storage
storePath | storage location of SQlite database and other files stored

Databases and tables are created dynamically. 
* Tables are named per forecast data source. 
* For [DWD](#dwd-configuration), table `dwd` contains data from `MOSMIX_L` and `dwd_s` from `MOSMIX_S`
* [Entso-E](#entso-e-configuration) and [CO2signal](#co2signal-configuration) create a table for each zone, `entso_<zone>` and `co2signal_<zone>` respectively.

_Influx_ stores a reduced set of data, aimed at displaying forecast data in a dashboard or similar. _SQLite_ is tailored to build a data repository useful for deeper analysis and learning.

All times stored or reported are in UTC. All period time stamps are aligned to show the _periodEnd_. Hence, at times, data appears to be mis-aligned with directly downloaded data from the data source. This is because some sources report period timestamps as _periodStart_.

### SQLite Storage
```
[DBRepo]
    dbName  = pvforecasts.db      # SQLite database name (at 'storePath')
```
An SQLite database is dynamically created with above defined name at `storePath` with name `dbName`. It is sufficient to remove the database to cause a re-creation of a fresh database. If the configuration is changed on an existing data, new tables are added dynamically. Fields which no longer exist are left empty. But new fields are _not_ added dynamically.

The following features are only available in _SQLite_ storage:
* All tables except `solcast` contain the minimum set of weather parameters as tabled [above](#convert-weather-data-to-irradiation-data). In addition, for each [irradiation model](#convert-irradiation-data-to-pv-output-power) enabled, GHI, DHI and DNI are stored alongside estimated PV ac and dc output power. These parameters may be multiplied depending on [split-array system configurations](#split-array-system-configuration) used.

* If the configuration parameter `dropWeather` is disabled (set to `0`), all (other) weather parameters of the forecast source are also stored, with their original names and units. By default (`dropWeather = 1`) only the [used parameters](#convert-weather-data-to-irradiation-data) are stored

* All tables contain `IssueTime` (when forecast was issued) and `PeriodEnd` (end time of forecast period). Date from previous `IssueTime` are not deleted to allow analysis of accuracy of forecasts over different forecast horizons. This makes the database grow quickly however!

### Influx Storage

_Influx_ contains a reduced set of data, compared to _SQLite_:

* the last forecast overwrites any older forecast for a certain forecast time. That is, the _Influx_ database always contains the _current best knowledge_ about the forecasted parameter.
* For modelled PV output power forecasts only contains DC power estimates, named `dc_<model>` for the [irradiance](#convert-weather-data-to-irradiation-data) model(s) calculated

[Influx](https://www.influxdata.com/products/influxdb/) has undergone a major, largely not backward compatible upgrade between version 1.x and 2.x. However, both version are supported (though not in parallel). _Influx 1.x_ is out of maintenance since 2021. Hence, for new installations, it is suggested to move to _Influx 2.6_ or newer.

#### Influx v2.x Storage
Instead of Influx v1.x storage, Influx v2.x can be used. For this to work, the config file section must adhere to the following:
```
[Influx]
    influx_V2       = 1              # enable Influx 2.x support (default is to use 1.x)
    token           = <your token>
    org             = <your org>
    bucket          = <your bucket>  # fall-back: use key `database`
```

_Tables_ are called _buckets_ but largely serve the same purpose.
Note that in Influx 2.x token based authentication is mandatory. Tokens can be [generated](https://docs.influxdata.com/influxdb/cloud/security/tokens/create-token/) in the Influx GUI.

#### Influx v1.x Storage
```
[Influx]
    host              = <your_hostname>         # default: localhost
    # port            = 8086
    database          = <your_influx_db_name>
    # username        = root
    # password        = root
    # retention       = None                    # retention policy   
```

_Tables_ are called _measurements_ but serve the same purpose.

If authentication is required, optional `username` and `password` can be provided in the `[Influx]` config section. Default is `root` / `root` (as is the default for Influx 1.x). Authentication is *not* SSL encrypted though.

If the database is configured to support multiple retention policies, one for the _PVForecast_ data can be selected with `retention`. 

### .csv File Storage
`storeCSV = 1` store output in .csv files at `storePath`. This is mainly for debugging. 

_SolCast_ can only store to csv files if at least one other storage model (SQlite, Influx) is enabled.



## Version History
**v2.11.01**    2023-08-05
Bug fix
+ proper version checking of pvlib (`pip install packaging` might be needed) 

**v2.11.00**    2023-04-21
Bug fixes
+ SolCast interval calculation fixed for low number of `apiCalls`
+ avoid exit, if some forcast providers cause errors (eg. _too many API calls_) - allow continuation with next forecast provider
+ other bug fixes

_Compatibility notes on v2.11.00_

_SolCast_ has changed number of allowed `apiCalls` per day to 10, but it appears that legacy users still can use their previous entitlements. The default value for `apiCalls` has changed, so that legacy users now need explicitly set their entitlement value.

**v2.10.00**    2023-02-28

If you plan to continue using only _SolCastLight_, there is no reason to update - but you miss out on the new capabilities on CO2 intensity forecast
+ [CO2 intensity forecast](CO2Intensity) added, see [Entso-E](#entso-e-configuration) and [CO2signal](#co2signal-configuration)
+ _SolCast_ interval can now be configured to `24h` - see [SolCast Configuration](#solcast-configuration). This solves [issue #15](https://github.com/StefaE/PVForecast/issues/15)
+ Installation simplified - if some libraries are not installed, _PVForecast_ behaves gracefully and only disables functionality which cannot be maintained. See [Installation](#installation)
+ it is no longer required to create Influx databases manually upfront
+ documentation (including [pages](https://stefae.github.io/PVForecast/)) reworked
+ bug fixes

_Compatibility notes on v2.10.00_

+ `[Forecasts]` key `OWM` has been renamed to `OpenWeatherMap` for consistency reasons
+ default model changed from `CEC` to `PVWatts`, see [Convert Irradiation Data to PV Output Power](#convert-irradiation-data-to-pv-output-power)

**v2.01.00**    2022-12-03
+ solves [issue #14](https://github.com/StefaE/PVForecast/issues/14): [SolCast](#solcast-configuration) defaults to 48h, but accepts an `hours` parameter.
+ Upgrade notice: for this to work, `pysolcast` version needs be v1.0.2 or higher

**v2.00.00**    2022-07-24
+ added [VisualCrossing](#visualcrossing-configuration) as new forecast source
+ added [File Input](#fileinput-configuration) as new forecast source, to simplify debugging
+ [MOSMIX](#dwd-configuration) cloud based models use parameter `Neff` (effective cloud coverage) instead of `N` (cloud coverage) for slightly improved accuracy.
+ default [Irradiation model](#convert-weather-data-to-irradiation-data) changed from `all` to `disc` (`clearsky_scaling` for cloud data)
+ documentation improved
+ code refactoring: weather parameters are now renamed and converted to standard units in the respective source objects rather than `PVModel`

_Compatibility notes on v2.00.00_

There are no changes if you are using _SolcastLight_ and hence, there is no reason to update. However, if the full version is used, the following changes apply:
+ changes to [Influx Storage](#influx-v1x-storage): Cloud based forecast fields have new (shorter) names. Influx will transparently add new fields, but long-term trends will get broken.
+ changes to [SQLite Storage](#sqlite-storage):
  + tables `dwd` and `pvsystem` are consolidated into `dwd`. Likewise, tables `dwd_s` and `pvsystem_s` are consolidated into `dwd_s`
  + weather data in tables `dwd`, `owm` and `visualcrossing` have standard names and units as documented [above](#convert-irradiation-data-to-pv-output-power)
  + other weather parameters are only stored if `dropWeather = 0` for the respective data source

As a consequence, if the [SQLite Storage](#sqlite-storage) model is used, the pre-existing database (referenced by `DBRepo.dbName`) has to be deleted, so that a new version, with new tables and fields, will automatically be re-created on first execution of the script.

**v1.03.00**
+ updated readme file, fixing some documentation bugs

**v1.02.00**
+ [Influx 1.x](#influx-v1x-storage) now supports authentication
+ small bug fixes

**v1.01.00**    2021-03-28
+ SolCast:
  - [SolCast](#solcast-configuration) default `interval` management to make optimal use of permitted 50 API calls/day
  - [split array support](#split-array-system-configuration) for MOSMIX and OWM (SolCast supports two arrays only)
- [Influx v2.x](#influx-v2x-storage) support
- [storeCSV](#csv-file-storage) now enabled for all data sources
- various bug fixes, documentation improvement

v1.00.00    2021-02-06  initial public release

### Deprecations
* **Deprecated by SolCast**: Solcast previously allowed to post PV performance data to [tune forecast](https://articles.solcast.com.au/en/articles/2366323-pv-tuning-technology) to eg. local shadowing conditions, etc. 

* `SolCastLight` is deprecated (but still available). Use `python PVForecast.py -c solcast_light_config.ini` instead

## Acknowlegements
Thanks to all who raised issues or helped in testing!

## License and Disclaimer
Distributed under the terms of the [GNU General Public License v3](https://github.com/StefaE/PVForecast/blob/main/LICENSE)

The software pulls data from various weather sources. It is the users responsibility to adhere to the use conditions of these sources. 

The author cannot provide any warranty concerning the availability, accessability or correctness of such weather data and/or the correct computation of derived data for any specific use case or purpose. Further warranty limitations are implied by the license
