---
title: Introduction
layout: template
order: 1
filename: index
--- 

# PVForecast Introduction
Forecasts to optimize electricity consumption for rooftop PV (photo-voltaic) installations

----------- 
## Table of Content

  - [Introduction](#introduction)
  - [PV Production Output Forecasts](#pv-production-output-forecasts)
  - [CO2 Intensity Forecast <span style="color:#00B0F0"><b>new</b></span>](#co2-intensity-forecast)
  - [Data Storage](#data-storage)
  - [Sister Projects](#sister-projects)
  - [License and Disclaimer](#license-and-disclaimer)

-----------

## Introduction
The project described here is developed in Python 3 and intended to run on Raspberries. It integrates with [solaranzeige](https://solaranzeige.de), which allows easy monitoring of a PV system.

* The [Users Guide](README) provides a full description of installation and configuration procedures.
* For ideas and questions, use the [Discussions](https://github.com/StefaE/PVForecast/discussions) section on Github.
* If things don't work as they should, raise an [Issue](https://github.com/StefaE/PVForecast/issues) in Github.
  
## PV Production Output Forecasts
If one wants to forecast PV production output over the coming hours or days, two options exist:
* usa a solar forecast provider which directly predicts output power for a predefined installation. The most prominent and accurate is probably [SolCast](https://solcast.com/)
* use a weather forecast provider which also predicts solar radiation (GHI), or at the very least a cloud coverage estimation (at the cost of accurracy)
	+ [Deutscher Wetterdienst](https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/met_verfahren_mosmix.html)
	+ [Visual Crossing](https://www.visualcrossing.com/)
	+ [Open Weather Map](https://openweathermap.org/)<span style="font-size:0.8rem"> - only cloud based forecast, hence less accurate</span>

This project supports all of the above. For the second group, modeling of the PV installation is required, which is done with the help of [pvlib](https://pvlib-python.readthedocs.io/en/stable/). Support for split array configurations (eg. east _and_ west oriented panels) is provided.

See [PV Output](PVOutput) for more introductionary details

## CO2 Intensity Forecast
<span style="color:#00B0F0"><b>new</b></span>

In a perfect world, the PV rooftop installation would allow for a fully self-sufficient energy supply. Unfortunately, this is not the case: In winter and cloudy weather we have to rely on grid power.

But not all grid power is equal: Sometimes, the grid is supplied from wind (and hence at a low CO2 intensity), sometimes from coal or other carbon sources. Hence, it matters when heavy consumers (such as BEV charging or heat pumps) are operated. The CO2 intensity forecast capabilities support such decisions: It puts us in a position to select periods with a low CO2 footprint for such consumption.

See [CO2 Intensity](CO2Intensity) for more introductionary details

## Data Storage
Independent of the data source - data wants to be stored. **PVForecast** supports a number of storage models:
* [SQLite](https://www.sqlite.org/index.html) - a file based relation database
* [Influx](https://www.influxdata.com/products/influxdb/) - a database optimized for time series storage
* Storage to _csv_ files is also possible

_Influx_ has undergone a major, largely not backward compatible upgrade between version 1.x and 2.x. Luckily, both version are supported by **PVForecast**

_Influx_ storage will overwrite any forecasts with newest values, whereas _SQLite_ will store all forecast horizons. This is useful to research forecast accuracy.

## Sister Projects
* [PVOptimize](https://github.com/StefaE/PVOptimize) optimizes energy usage produced by a rooftop PV system
* [PVControl](https://github.com/StefaE/PVControl) is a GUI to control **PVOptimize**

## License and Disclaimer
Distributed under the terms of the [GNU General Public License v3](https://github.com/StefaE/PVForecast/blob/main/LICENSE)

The software pulls data from various weather sources. It is the users responsibility to adhere to the use conditions of these sources. 

The author cannot provide any warranty concerning the availability, accessability or correctness of such data and/or the correct computation of derived data for any specific use case or purpose. Further warranty limitations are implied by the license.

