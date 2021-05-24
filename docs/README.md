# PVForecast
Rooftop PV production forecast (pages version)
 
## Introduction
This project supports an extensive set of production forecasts for PV rooftop installations. Various weather [data sources](#forecast-sources), [PV modeling algorithms](#forecast-models) and [storage methods](#data-storage) for results can be used. Split array PV installations are supported.

The project has been developped on Python3 and runs on Raspberries and integrates with [solaranzeige](https://solaranzeige.de) (see [Solaranzeige Integration](#solaranzeige-integration))

Generally, functionality is configured through a configuration file (default: `.\config.ini`, `.\solcast_light_config.ini`, a different location can be provided with `-c` command line option)

Two main scripts are provided:

Script | Description
-------|------------
`PVForecasts.py` | enables all functionality described in this `ReadMe`
`SolCastLight.py` | can only use [Solcast](https://solcast.com/) forecasts but is significantly easier to install and configure

## Disclaimer
The software pulls weather data from various weather sources. It is the users responsability to adhere to the use conditions of these sources. 

The author cannot provide any warranty concerning the availability, accessability or correctness of such weather data and/or the correct computation of derieved data for any specific use case or purpose.

Further warranty limitations are implied by the license

## License
Distributed under the terms of the GNU General Public License v3.
