# PVForecast
Rooftop PV production forecast (pages)
 
## Introduction
This project supports an extensive set of production forecasts for PV rooftop installations. Various weather [data sources](#forecast-sources), [PV modeling algorithms](#forecast-models) and [storage methods](#data-storage) for results can be used. Split array PV installations are supported.

The project has been developped on Python3 and runs on Raspberries and integrates with [solaranzeige](https://solaranzeige.de) (see [Solaranzeige Integration](#solaranzeige-integration))

Generally, functionality is configured through a configuration file (default: `.\config.ini`, `.\solcast_light_config.ini`, a different location can be provided with `-c` command line option)

Two main scripts are provided:
Script | Description
-------|------------
`PVForecasts.py` | enables all functionality described in this `ReadMe`
`SolCastLight.py` | can only use [Solcast](https://solcast.com/) forecasts but is significantly easier to install and configure

## SolCastLight: Minimalistic Installation
The following description of the full script is relatively complex. Hence, this section describes the **minimalisic** needs to only run SolCast forecasting:
1. prepare Python to run the script:
   1. [Basic Installation](#the-basics)
   2. [add some Python modules](#minimal-requirements)
2. update `solcast_light_config.ini` to your SolCast registration
   1. [SolCast Configuration](#solcast-configuration)
   2. [Influx Storage Configuration](#influx-storage)
   3. (depricated): [SolCast Tuning Configuration](#solcast-tuning)
3. if integration with [Solaranzeige](https://solaranzeige.de) is desired, read [this](#solaranzeige-integration)
4. [Install and run script](#running-the-script)

A couple of more options can be configured, but are left out of this brief description. They would become obvious when reading the full text below.

-------------
## Table of Content
  * [Introduction](#introduction)
  * [SolCastLight: Minimalistic Installation](#solcastlight-minimalistic-installation)
  * [Main Functionality and Configuration](#main-functionality-and-configuration)
    + [Forecast Sources](#forecast-sources)
    + [**Solcast** Configuration](#solcast-configuration)
    + [**OWM** configuration](#owm-configuration)
    + [**MOSMIX** configuration](#mosmix-configuration)
    + [Forecast models](#forecast-models)
      - [Convert Weather Data to Irradation Data](#convert-weather-data-to-irradation-data)
      - [Convert Irradiation Data to PV Output Power](#convert-irradiation-data-to-pv-output-power)
      - [Split Array System Configuration](#split-array-system-configuration)
    + [Data Storage](#data-storage)
      - [SQLite Storage](#sqlite-storage)
      - [Influx v1.x Storage](#influx-v1x-storage)
      - [Influx v2.x Storage](#influx-v2x-storage)
      - [.csv File Storage](#csv-file-storage)
    + [Solaranzeige Integration](#solaranzeige-integration)
  * [Installation](#installation)
    + [The Basics](#the-basics)
    + [Minimal Requirements](#minimal-requirements)
    + [Full Installation](#full-installation)
    + [Optional](#optional)
  * [Running the Script](#running-the-script)
  * [To Do](#to-do)
  * [Deprecated](#deprecated)
    + [Solcast Tuning](#solcast-tuning)
  * [Version History](#version-history)
  * [Acknowlegements](#acknowlegements)
  * [Disclaimer](#disclaimer)
  * [License](#license)

Table of contents generated with [markdown-toc](http://ecotrust-canada.github.io/markdown-toc/)

-------------

The reminder of this `ReadMe` file is meant to describe the full script configuration. 

## Main Functionality and Configuration
`.\config.ini` is a configuration file parsed with python's [configparser](https://docs.python.org/3/library/configparser.html). Most importantly:
* items can be promoted to the `[DEFAULT]` section if same `key = value` pair is used in multiple sections
* inline comments are configured to start with `#`
* multi-line values are not allowed
* out-commented `key = value` pairs show the respective default options, which could be changed as needed

The `config.ini` file provided with the distribution contains a few site specific values, which cannot be pre-configured. The are shown as `<xx>`. This file should be read alongside the below text for best understanding.

### Forecast Sources
```
[Forecasts]                       # enable / disable certain forecasts
    Solcast           = 1         
    OWM               = 0         # OpenWeatherMap.org
    MOSMIX_L          = 0         # single station file, updated every 6h
    MOSMIX_S          = 0         # all stations,        updated hourly download
```

Forecast Sources can be (dis-)enabled with 0 or 1. Any number of sources can be enabled simultaneously.

Source | Description
-------|------------
**Solcast** | Solar forecast by [Solcast](https://solcast.com/)
**OWM** | Weather forecast from [OpenWeatherMap.org](https://openweathermap.org/) with approx. 10 parameters
**MOSMIX** | provided by [Deutscher Wetterdienst](https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/met_verfahren_mosmix.html) (primarily for Germany). Two flavours exist: 
_MOSMIX_L_| single station forecast, updated four times per day and approx. 115 weather parameters
_MOSMIX_S_| comprehensive download file of all MOSMIX weather stations, updated hourly, containing approx. 40 weather parameters. **NOTE:** MOSMIX_S causes the download of a ~37MByte file every hour - ensure that you really want to do that and that you have enough internet bandwidth!

Depending on the data source, various forecast algorithms are available. The configuration happens in the respective sections described below.

### **Solcast** Configuration
```
[SolCast]
    resource_id       = <resource_id_from_solcast.com>
    # resource_id_2   = <second_resource_id_from_solcast.com>
    api_key           = <api_id_from_solcast.com>
    # interval        =  0        # interval at which SolCast is read (during daylight only)
    # Latitude        = 50.2      # defaults describe Frankfurt, Germany
    # Longitude       =  8.7
```

[Solcast](https://solcast.com/pricing/) allows for the free registration of a residental rooftop PV installation of up to 1MWp and allows for up to 50 API calls/day. The registration process provides a 12-digit _resource_id_ (`xxxx-xxxx-xxxx-xxxx`) and a 32 character API key.

Solcast directly provides a PV forecast (in kW) for 30min intervals, with 10% and 90% confidence level. Hence, no further modelling is needed.

[Since tuning was deprecated](https://articles.solcast.com.au/en/articles/4945263-pv-tuning-discontinued), Solcast allows the definition of a second rooftop site to support dual-array setups (eg., east/west). In such a situation, an additional `resource_id_2` can be provided. It will be queried at the same times as `resource_id`. Individual and total forecast results will be stored in the database(s)

To stay within the limits of 50 API calls/day, the script calls the API only between sunrise and sunset. It can further manage the calling interval to the API automatically or explicitly through the value assigned to `interval`:

value | meaning
------|---------
0     | **Default**: call API every 15min (single array) or 30min (dual-array). To not exceed maximum API calls, extend interval to 30min (60min) after sunrise and before sunset on long days. Hence, this provides most accurate (short-term) forecasts during mid-day.
early | same as `0`, but all interval extensions are done before sunset only. Hence, this provides most accurate forecasts in the morning
late  | same as `0`, but all intervall extensions are done after sunrise only. Hence, this provides most accurate forecasts in the afternoon
number | a positive number (eg. 15, 30, 60, ...) ensures that the API is not called more frequently than the stated number of minues.

There is obviously an interaction between the `interval` settings and the `crontab` entry used to run the script (see [below](#running-the-script)). It is suggested to configure `crontab` to run the script every 15 minutes.

Purpose of `Latitude` and `Longitude` parameters (which maybe better placed in `[Default]` section, if weather based forecasts, as described in the following sections, are also calculated) is to know sunrise and sunset times. Defaults are for Frankfurt, Germany.

### **OWM** configuration
```
[OpenWeatherMap]
    api_key           = <api_id_from_openweathermap.org>
    Irradiance        = all       # irrandiance model (for OWM)
```

[OpenWeatherMap](https://openweathermap.org/price) offers free access to their API to regularly download weather forecasts. The registration process provides a 32 character API key.

The weather forecast consists of approx. 10 parameters, including cloud coverage, which can be modelled to a PV forecast (see [Forecast Models](#forecast-models)). The modelling strategy is controlled with the `Irradiance` parameter as described below.

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

Unlike modern APIs, _Deutscher Wetterdienst_ (DWD) allows only file download for what they call [MOSMIX data](https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/met_verfahren_mosmix.html). Hence, the software described here has to accomodate for the associated complications.

Two download schemes (as described [above](#forecast-sources)) exist. Keys `DWD_URL_L` and `DWD_URL_S` provide the respective stems of download links. The station abreviation needs be taken from [their website](https://wettwarn.de/mosmix/mosmix.html)

`storeKMZ`: The files downloaded are named `*.kmz` which is inadequate in two ways: First, the files are simple `.zip` files (so, why are they not called that way?) and second, a `.zip` file is meant to contain multiple files, which clearly the `.kmz` files never do. Hence, with `storeKMZ = 1`, downloaded data is stored in the more adequate `.gz` format. For _MOSMIX_L_, the downloaded files for the selected station are stored. For _MOSMIX_S_, an extract for the selected station is stored in a self-contained compressed `.xml` file. That format is very similar to _MOSMIX_L_ files.

`keepKMZ_S`: in case of downloading the (huge) _MOSMIX_S_ file, they can be stored by enabling this option. **Note** that approx. 900MByte/day of storage space will be consumed!

The modelling strategy used to convert weather data to irradiance is controlled with the `Irradiance` parameter as described in the next section.

### Forecast models
Data from [OWM](#owm-configuration) and [MOSMIX](#mosmix-configuration) do not directly contain PV output power. This needs be modelled using functionality provided by [pvlib](https://pvlib-python.readthedocs.io/en/stable/). Multiple modelling approaches are supported, selected by the `Irradiance` parameter seen above. 

Essentially, the modelling consists of a two-step approach:
1. convert weather data to irradiation data (GHI, DNI, DHI). Multiple conversion strategies are available and controlled with the `irradiance` parameter in the config section for `[DWD]` and `[OpenWeatherMap]`

2. convert such irradiation data into PV output power. This is controlled in the config section `[PVSystem]`

#### Convert Weather Data to Irradation Data

Model | Input parameter | Applicable to | Comment
------|-----------------|---------------|--------
[disc](https://pvlib-python.readthedocs.io/en/stable/generated/pvlib.irradiance.disc.html)  | Rad1h (GHI)     | MOSMIX | not all stations have Rad1h, probably the 'standard' model
[dirint](https://pvlib-python.readthedocs.io/en/stable/generated/pvlib.irradiance.dirint.html) | Rad1h (GHI) | MOSMIX | not all stations have Rad1h
[dirindex](https://pvlib-python.readthedocs.io/en/stable/generated/pvlib.irradiance.dirindex.html) |Rad1h (GHI) | MOSMIX | not all stations have Rad1h, some numerical instabilities at very low values of GHI
[erbs](https://pvlib-python.readthedocs.io/en/stable/generated/pvlib.irradiance.erbs.html) | Rad1h (GHI) | MOSMIX | not all stations have Rad1h
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
In this section, we first describe how to model a single array PV System. The software also supports the configuration of split array systems. The necessary extensions are described in the next section.

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
    # based on .csv files at .../lib/python3.8/site-packages/pvlib/data, special characters to be replaced by '_'
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
The .csv are stored whereever pvlib installs on your system. This place can be found with
`pip3 show pvlib` which returns something like:
<pre>
Name: pvlib
Version: 0.8.1
Summary: A set of functions and classes for simulating the performance of photovoltaic energy systems.
Home-page: https://github.com/pvlib/pvlib-python
Author: pvlib python Developers
Author-email: None
License: BSD 3-Clause
Location: <b>installation_location</b>
Requires: requests, scipy, numpy, pytz, pandas
Required-by: 
</pre>

From this, you'll find in `installation_location/pvlib/data` two `.csv` files `sam-library-cec-inverters-2019-03-05.csv` and `sam-library-cec-modules-2019-03-05.csv` for inverters and modules respectively. The first column contain the names of supported inverters and modules. 

Special characters and blanks need replaced with `_` in the config file. Hence, eg. `SMA America: SB10000TL-US [240V]` becomes `SMA_America__SB10000TL_US__240V_`

If the (default) `CEC` approach is used, the selected model should at a minimum match the nameplate power of the installed panels (eg. 325Wp). The selected inverter is uncritical as long as the nameplate power is same or higher as installed inverter (eg. 10kW) - the modeling of inverters is relatively poor in pvlib, considering only a _NominalEfficency_.

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
    Latitude          = 51.8
    Longitude         =  6.1
    Altitude          =  74       # altitude of system (above sea level)
    Tilt              =  30
    Azimuth           = 127       # 270=West, 180=South, 90=East
```
Since latitude and longitude parameters are also needed by [Solcast](#solcast-configuration) to calculate sunrise and sunset, it is efficient to put these two parameters into the `[Default]` section of the configuration file.

#### Split Array System Configuration
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

PV output is calculated for each sub-array and creates parameters `dc_<irradiation_model>_<suffix>` and `ac_<irradiation_model>_<suffix>`. The parameter `storage` controls what is handed to the [data storage](#data-storage) module. Valid values are:

Value | Function
------|---------
sum | **default**: only sum of all sub-arrays is stored (as `dc_/ac_<irradiation_model>`)
individual | only the individual sub-array results are stored, but sum is not calculated
both | individual results and sum are stored

### Data Storage
Forecasting PV output power would be pointless, if the resulting data wouldn't be stored anywhere. The application supports three storage models:
1. SQLite (file based relational database)
2. Influx
3. csv files

The following configuration parameters control what is stored where and can be configured separately in sections `[SolCast], [OpenWeatherMap], [DWD]` or commonly in section `[Default]` (0 = disable, 1 = enable)

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

Note that if the configuration file is changed on a running system, more or less data maybe calculated:
* newly needed tables are created on-the-fly
* dropped fields are simply left empty (which SQLite handles relatively efficiently)
* however, new fields are not added dynamically - it is advised to drop the old database in such cases, which causes dynamic creation of a new one.

#### Influx v1.x Storage
```
[Influx]
    host              = <your_hostname>         # default: localhost
    # port            = 8086
    database          = <your_influx_db_name>   
```

This will create the following _measurements_ (akin tables) in the defined Influx database:
Table | Content
------|--------
solcast | power estimates: `pv_estimate`, `pv_estimate10`, `pv_estimate90`
owm     | DC power estimates from OpenWeatherMap, named `dc_<model>`
pvsystem | DC power estimates from MOSMIX_L, named `dc_<model>`
pvsystem_s | DC power estimates from MOSMIX_S, named `dc_<model>`
forecast_log | log table on data downloads from [forecast sources](#forecast-sources) (this is required for internal purposes)

where `<model>` refers to one of the [irradiance](#convert-weather-data-to-irradation-data) models calculated

The `database` must pre-exist in Influx. If it does not, the following manual operations can create it:
```
~ $ influx
> show databases
> create database <your_influx_db_name>
> show databases
> quit
~ $
```
If authentication is required, optional `username` and `password` can be provided in the `[Influx]` config section. Default is `root` / `root` (as is the default for Influx 1.x). Authentication is *not* SSL encrypted though.

#### Influx v2.x Storage
Instead of Influx v1.x storage, Influx v2.x can be used. For this to work, the config file section must adhere to the following:
```
[Influx]
    influx_V2       = 1              # enable Influx 2.x support
    token           = <your token>
    org             = <your org>
    # optionally, the entry database can be named bucket. If not existent, the database is used
    # to identify what is called the bucket in Influx v2.x
    # bucket        = <your_influx_bucket_name>
```

Note that in Influx 2.x token based authentification is mandatory

#### .csv File Storage
`storeCSV = 1` store output in .csv files at `storePath`. This is mainly for debugging. 

SolCast can only store to csv files if at least one other storage model (SQlite, Influx) is enabled.

### Solaranzeige Integration
This application is designed to run seamlessly alongside [solaranzeige](https://solaranzeige.de). Hence, if installed on the same host, the `[Influx]` configuration section discussed in previous section may very well look like this:
```
[Influx]
    # host            = localhost             # default: localhost
    database          = solaranzeige   
    power_field       = PV.Gesamtleistung
```
This will add the discussed _measurements_ to the `solaranzeige` database and make them immediatly available for display in Grafana.

The `power_field` is dependent on the inverter: Most have either a field `Gesamtleistung` or `Leistung`, reflecting the PV DC power.

## Installation
Installation mainly ensures that all necessary python modules are available. We assume a Raspberry host here - although the instructions are probably quite generic.

### The Basics
It is assumed that Python 3.x is available and pandas, numpy installed. This can be checked with the following commands:
```
~ $ python3
>>> import pandas as pd
>>> import numpy as np
>>> pd.__version__
>>> np.__version__
>>> quit()
~ $
```

If errors are seen, checkout [pandas installation instructions](https://pandas.pydata.org/pandas-docs/stable/getting_started/install.html) and use
```
sudo apt install python3-pandas
```

pandas versions from 1.1.2 and numpy  1.19.2 are known to work. Earlier versions might need an upgrade. Try the script and see what happens before you upgrade though. Some googling might be needed as on Raspberries the upgrade path is not always as linear.

In case [Influx Storage](#influx-storage) is desired, but `Influx` is not yet available, installation instructions can be found [here](https://simonhearne.com/2020/pi-influx-grafana/)

### Minimal Requirements
```
sudo pip3 install pysolcast                  # enables access to SolCast
sudo pip3 install astral                     # provides sunrise, sunset
sudo pip3 install influxdb                   # provides access to InfluxDB
```

With this we are able to run `SolCastLight.py`, which is limited to supporting Solcast as the only [forecast source](#forecast-sources)

### Full Installation
Other [forecast sources](#forecast-sources) require modelling a photovoltaic system, which is acheived using [pvlib](https://pvlib-python.readthedocs.io/en/stable/index.html). Unfortunatly, this library is not always straight forward to install - especially on 32-bit OS such as `Raspbian`. The default [install command]( https://pvlib-python.readthedocs.io/en/stable/installation.html)
```
sudo pip3 install pvlib[optional]
```
will likely fail - if it succeeds, you are the lucky guy. But what if not?

Some parts of `pvlib` require `nrel-pysam`, which only runs on 64-bit versions of Python, which we don't have on `Raspbian` ... so we might get something like
```
Command "python setup.py egg_info" failed with error code 1 in /tmp/pip-install-7twe_oqh/nrel-pysam/
```
What worked for me was following instructions [here](https://raspberrypi.stackexchange.com/questions/104791/installing-netcdf4-on-raspberry-3b) and do:
```
sudo apt-get install libhdf5-dev
sudo apt-get install libhdf5-serial-dev      # seems redundant, might be skipped
sudo python3 -m pip install h5py
sudo apt-get install netcdf-bin libnetcdf-dev
sudo python3 -m pip install netcdf4          # take a while ...

# siphon and tables are also needed by pvlib ...
sudo pip3 install siphon
sudo pip3 install tables
# ... and now it should work
sudo pip3 install pvlib
```

Finally, we might need (if not already installed by default) `elementpath` to handle `MOSMIX` .xml files:
```
sudo pip3 install elementpath
sudo pip3 install beautifulsoup4
```

### Optional
If [SQLite storage](#sqlite-storage) is configured, you'll end up with an SQLite database which you might want inspect. A great way (but by far not the only one) to do that is with [SQLite Browser](https://sqlitebrowser.org/)
```
sudo apt-get install sqlitebrowser
```

## Running the Script
After downloading the script from Github, into a directory of your choosing (eg. `\home\pi\PV`), you should have these files (and some more):
```
./PVForecasts.py
./SolCastLight.py
./config.ini
./solcast_light_config.ini
./PVForecast/*.py        # approx. 9 .py files
```

* update the config file (`config.ini` or `solcast_light_config.ini`, depending which version you want to run
* try it out ...: `python3 PVForecast.py` or `python3 SolCastLight.py`
* install it in `cron`

A typical `crontab` entry can look like so (assuming you have downloaded into `\home\pi\PV`):
```
*/15 * * * * cd /home/pi/PV && /usr/bin/python3 SolCastLight.py >> /home/pi/PV/err.txt 2>&1
```
which would run the script every 15min (recommended). 
+ 15min interval is recommended due to the API call management provided for [SolCast](#solcast-configuration). For other data sources, the script handles larger calling intervals internally.
+ Replace `SolCastLight.py` with the `PVForecast.py` to run the full script.

A great explanation of `cron` is [here](https://crontab.guru/examples.html). Crontab entries are made with `crontab -e` and checked with `crontab -l`.

**Note:** The script doesn't do much in terms of housekeeping (eg., limit size of SQLite database or `err.txt` file used above to redirect error messages).

## To Do
* more clever use of 50 allowed API calls/day for SolCast

## Deprecated
Following subjects have been deprecated by the data providers. They are still supported by `PVForecast` as some functionality still seems to work.

### Solcast Tuning
**Deprecated by SolCast**: Solcast previously allowed to post PV performance data to [tune forecast](https://articles.solcast.com.au/en/articles/2366323-pv-tuning-technology) to eg. local shadowing conditions, etc. 

```
[SolCast]
    post = 1
```
in the configuration file. But of course, it requires that such performance data is available locally.

The script assumes that performance data is available in the same Influx database as configured for forecast data storage. Saying
```
[Influx]
    database      = <your_influx_db_name>
    power_field   = PV.Gesamtleistung
    power_field_2 = PV.Leistung_Str_2
```
assumes that `<your_influx_db_name>` contains a measurement (table) `PV` with a field `Gesamtleistung` which has regular recordings of the PV generated power. 

For split array configurations (allowed by SolCast since official deprecation of tuning), a secondary tuning field `power_field_2` can be defined. In posting, `power_field` will be associated with `resource_id` and `power_field_2` with `resource_id_2`. This still seems to work as of today (2021-03-21). See [Solcast Configuration](#solcast-configuration) on guidence for split array support.

It is assumed that 
* this field has at least a time resolution of 5 minutes or less
* power is in W
* Influx stores times internally always as UTC (this is not actually an assumption, rather a fact, which the application storing power data must be aware of)

**Influx 2.0** is not supported for SolCast posting (this would need an update in `influx.py` for procedure `getPostData`)


## Version History
v1.00.00    2021-02-06  initial public release

v1.01.00    2021-03-28
+ SolCast:
  - [SolCast](#solcast-configuration) default `interval` management to make optimal use of permitted 50 API calls/day
  - [split array support](#split-array-system-configuration) for MOSMIX and OWM (SolCast supports two arrays only)
- [Influx v2.x](#influx-v2x-storage) support
- [storeCSV](#csv-file-storage) now enabled for all data sources
- various bug fixes, documentation improvement

v1.02.00
+ [Influx 1.x](#influx-v1x-storage) now supports authentication
+ small bug fixes

## Acknowlegements
Thanks to all who raised issues or helped in testing!

## Disclaimer
The software pulls weather data from various weather sources. It is the users responsability to adhere to the use conditions of these sources. 

The author cannot provide any warranty concerning the availability, accessability or correctness of such weather data and/or the correct computation of derieved data for any specific use case or purpose.

Further warranty limitations are implied by the license

## License
Distributed under the terms of the GNU General Public License v3.
