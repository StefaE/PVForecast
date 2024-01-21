'''
SolCast is constrained in number of API calls/day. SolCast.py tries to use these credits strategically
This debugger script uses the same calculations as in solcast.py and hence allows to debug the
implemented statistics.

Run from command prompt - no further input needed (but view inline comments below)
'''

from astral            import LocationInfo
from astral.sun        import sun
from datetime          import datetime, timedelta, timezone
from math              import floor

# --------------------------------------------------------------------------- User Input required here
location     = LocationInfo('na', 'na', 'UTC', latitude=50.2, longitude=8.7)      # Frankfurt: 50.2N / 8.7E
day          = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)                 # day, from which to run

DAYS         = 365                                                              # number of days to run (more verbose output if DAYS = 1)
INTERVAL     =   0                                                                # interval used (as in solcast.py: 0 .. -3)
apiCalls     =  10                                                                # available API credits
isDualArray  = True                                                               # whether we have a dual-array config
# --------------------------------------------------------------------------- End of User Input

if isDualArray:
    apiCalls = floor(apiCalls/2)

if apiCalls > 24: DELTAMIN = 15
else:             DELTAMIN = 30

credits_used = []
allSteps     = []
tot_used     =  0
for i in range(DAYS):
    now_utc = day
    
    last_issue   = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    mySun        = sun(location.observer, date=now_utc)
    daylight_min = (mySun['sunset'] - mySun['sunrise']).total_seconds()/60

    _n           = 0
    if DAYS==1:
        print("Sunrise= ", mySun['sunrise'], "; Sunset= ",  mySun['sunset'], "; Minutes= ", daylight_min)

    if apiCalls > 24: tick = 15
    else:             tick = 30
    if INTERVAL == -3:
        want_min = 24*60/apiCalls
        optimal = tick*floor(want_min/tick) + tick
    else:
        want_min = daylight_min/apiCalls
        optimal = tick*floor(want_min/tick)
        if optimal == 0: optimal = tick
    if DAYS==1:
        print("want= ", want_min, "; optimal= ", optimal)
    
    need = int((int(daylight_min)+1)/optimal)+1     # number of 'optimal' minute intervals between sunrise and sunset
    long = need - apiCalls                                                                         # number of times where we can only call at longer intervals

    n = 0
    stepSize = []
    for j in range(int(1440/DELTAMIN)):
        now_utc = now_utc+timedelta(minutes=DELTAMIN)
        delta_t  = round((now_utc - last_issue).total_seconds()/60)
        interval = INTERVAL
        if interval == -3 or (now_utc > mySun['sunrise'] and now_utc < mySun['sunset']):
            if   interval ==  0 and  ((now_utc - mySun['sunrise']).total_seconds()/60 < long*optimal or (mySun['sunset'] - now_utc).total_seconds()/60 < long*optimal):
                interval = optimal*2
            elif interval == -1 and (now_utc - mySun['sunrise']).total_seconds()/60 < long*optimal*2:    # focus on late,  neglect early
                interval = optimal*2
            elif interval == -2 and (mySun['sunset'] - now_utc).total_seconds()/60 < long*optimal*2:     # focus on early, neglect late
                interval = optimal*2
            elif interval == -3:                                                                         # download in regular intervals during full day (24h)
                interval = optimal
            else:
                interval = optimal
            if delta_t > interval - 2:
                n = n + 1
                if DAYS == 1:
                    print(n, " -- ", now_utc, "; delta_t = ", delta_t)
                if delta_t < 1440: stepSize.append(delta_t)
                last_issue = now_utc
            elif DAYS == 1:
                nextDL = now_utc + timedelta(minutes= interval - delta_t)
                if INTERVAL != -3:
                    if (nextDL > mySun['sunset']):
                        nextDL = mySun['sunrise'] + timedelta(days=1)
                print("Message - Solcast download inhibted to preserve credits; next DL planned after (UTC): " + nextDL.strftime("%Y-%m-%d, %H:%M:%S"))
    print("day: ", day.date(), " nCalls= ", n, " Intervals used: ", set(stepSize))
    allSteps = allSteps + list(set(stepSize))
    credits_used.append(n)
    if n > apiCalls:
        print("----------------------- ERROR --- ", day)
    tot_used += n
    day     = day + timedelta(days=1)

print("--- overall run summary")
print("credits used: ", set(credits_used), " total = ", tot_used)
print("all steps: ", set(allSteps))
