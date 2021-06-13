# PVForecast
Rooftop PV production forecast (pages version)
 
## Introduction
This project supports an extensive set of production forecasts for PV rooftop installations. Various weather [data sources](#forecast-sources), [PV modeling algorithms](#forecast-models) and [storage methods](#data-storage) for results can be used. Split array PV installations are supported.

The project has been developped on Python3 and runs on Raspberries and integrates with [solaranzeige](https://solaranzeige.de) (see [Solaranzeige Integration](#solaranzeige-integration))

Two main scripts are provided:

Script | Description
-------|------------
`PVForecasts.py` | enables all functionality described in this `ReadMe`
`SolCastLight.py` | can only use [Solcast](https://solcast.com/) forecasts but is significantly easier to install and configure

A more detailed technical overview is provided [here](https://github.com/StefaE/PVForecast#readme)

----------- 
## Table of Content
  * [Introduction](#introduction)
  * [Functional overview and rough comparision](#functional-overview-and-rough-comparision)
    + [Traditional weather services](#traditional-weather-services)
    + [Solcast](#solcast)
    + [Forcast horizon](#forcast-horizon)
    + [Quantifyng forecast quality](#quantifyng-forecast-quality)
  * [Disclaimer](#disclaimer)
  * [License](#license)

<small><i><a href='http://ecotrust-canada.github.io/markdown-toc/'>Table of contents generated with markdown-toc</a></i></small>

-----------

## Functional overview and rough comparision

### Traditional weather services

PV performance forecasts can be done from traditional weather data (supported providers: [Deutscher Wetterdienst](https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/), [OpenWeatherMap.org](https://openweathermap.org/)) 

They may provide solar radiation data (GHI) or just cloud data. Both can be used to generate a PV power forecast. The following picture shows the result - for a particularly bad day, April 29:

![Others](Others_April29.png)

Here, `disc` is based on GHI data from DWD/MOSMIX. As GHI data is not available for all stations, `clearsky_scaling_DWD` uses cloud coverage data from DWD/MOSMIX. Both are closely related, as also the following days show:

![MOSMIX](Disc_vs_Cloud.png)

In this example, GHI based forecasts (`disc`) seem to be slighty more optimistic than cloud based, but this is not always the case.

As with any weather forecast, different providers sometimes diverge. OpenWeatherMap only provides cloud coverage, so - for fairness - we should only compare this with cloud-based forcasts from DWD:

![MOSMIX_OWM](DWD_OWM.png)

Hmm... what to believe? Forecasts are difficult, especially those about the future!

### Solcast

[Solcast](https://solcast.com/) is specializing on worldwide PV performance forecasts, based on satellite imaging. They offer forecasts for rooftop installations free-of-charge for up to dual-array configurations.

The same time frame as shown above, in comparison to actual data:

![Solcast 8 Days](SolCast_8days.png)

For comparison reasons, also DWD (MOSMIX = `disc`) is shown. It seems obvious that SolCast does overall a much better job. It also provides a confidence interval (p10, p90) for its forecasts. We should hence expect taht for any 30min interval, actual PV output is in 80% of cases between these bounds.

### Forcast horizon

For the example of Solcast, we'll investigate a bit how forecasts evolve over different forecast horizons. Solcast is updating its forcast every 15min (although forcast intervals are always fixed at 30min). The maximum forecast horizon is 7 days.

Hence, if we look at eg. April 29th, we get the following picture. The concept described here is identical for other forecast providers, although forecast updates are much rarer (hourly, four-hourly)

![Forecast Development](SolCast_Apr29_Development.png)

Forecasts from the preceding days (April 23rd .. April 28th) are updated about once a day (greenish) and as accurate as other weather forecasts. However, on the current day (April 29th), forecasts are updated every 15min (blueish).

The red line indicates the latest (last) forecast for the respective 30min time period. 

Hence, for this particular day, long term forecasts from previous days were far too optimistic. Satellite based current day forecasts were quite stable in the morning, but trended to lower PV output in the afternoon.

Comparing these forecasts with actuals, show that on this exceptional day, Solcast was still overly optimistic betweeen 8:00 and 12:00 and actuals were even outside the confidence interval. This happens relatively rarely

![Actuals Comparison](SolCast_Apr29.png)

### Quantifying forecast quality

The above discussion motivates a deeper look at forecast quality as a function of forecast horizon: Which forecast is most accurate for current day / next day / future days?

Such data will eventually be published here, but it requires recording over an extended period in time.

The program discussed here supports different [storage models](../README.md#data-storage):
* SQLite storage model stores all data (ie., for every forecast `IssueTime`)
* Influx storage model stores only the respective latest forecast for each forecast `PeriodEnd`

Hence, Influx is useful to steer systems based on most recent forecast. SQLite allows to research forecast performance over forecast horizon.

## Disclaimer
The software pulls weather data from various weather sources. It is the users responsability to adhere to the use conditions of these sources. 

The author cannot provide any warranty concerning the availability, accessability or correctness of such weather data and/or the correct computation of derieved data for any specific use case or purpose.

Further warranty limitations are implied by the license

## License
Distributed under the terms of the GNU General Public License v3.
