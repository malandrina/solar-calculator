import datetime
import time
import json
import os
import sys

from math import radians, degrees, floor, sin, cos, tan, asin, acos, atan, atan2, pi
from datetime import datetime as dt

TIMEZONE = "US/Pacific"

def sunpos(when, location, refraction):
    # Extract the passed data
    year, month, day, hour, minute, second, timezone = when
    latitude, longitude = location

    # Convert latitude and longitude to radians
    rlat = radians(latitude)
    rlon = radians(longitude)

    # Decimal hour of the day at Greenwich
    greenwichtime = hour - timezone + minute / 60 + second / 3600

    # Days from J2000, accurate from 1901 to 2099
    daynum = 367 * year - 7 * (year + (month + 9) // 12) // 4 + 275 * month // 9 + day - 730531.5 + greenwichtime / 24
    #daynum = 367 * year - 7 * (year + (month + 9) // 12) // 4 - 3 * ((year + (month-9)//7 ) // 100 + 1) // 4 + 275 * month // 9 + day - 730515 # Another formula, which is valid over the entire Gregorian Calendar

    # Mean longitude of the sun
    mean_long = daynum * 0.01720279239 + 4.894967873

    # Mean anomaly of the Sun
    mean_anom = daynum * 0.01720197034 + 6.240040768

    # Ecliptic longitude of the sun
    eclip_long = mean_long + 0.03342305518 * sin(mean_anom) + 0.0003490658504 * sin(2 * mean_anom)

    # Obliquity of the ecliptic
    obliquity = 0.4090877234 - 0.000000006981317008 * daynum

    # Right ascension of the sun
    rasc = atan2(cos(obliquity) * sin(eclip_long), cos(eclip_long))

    # Declination of the sun
    decl = asin(sin(obliquity) * sin(eclip_long))

    # Local sidereal time
    sidereal = 4.894961213 + 6.300388099 * daynum + rlon

    # Hour angle of the sun
    hour_ang = sidereal - rasc

    # Local elevation of the sun
    elevation = asin(sin(decl) * sin(rlat) + cos(decl) * cos(rlat) * cos(hour_ang))

    # Local azimuth of the sun
    azimuth = atan2(-cos(decl) * cos(rlat) * sin(hour_ang), sin(decl) - sin(rlat) * sin(elevation))

    # Convert azimuth and elevation to degrees
    azimuth = into_range(degrees(azimuth), 0, 360)
    elevation = into_range(degrees(elevation), -180, 180)

    # Refraction correction (optional)
    if refraction:
        targ = radians((elevation + (10.3 / (elevation + 5.11))))
        elevation += (1.02 / tan(targ)) / 60

    # Return azimuth and elevation in degrees
    return azimuth, elevation

def suninfo(when, location):
    # Extract the passed data
    year, month, day, tz_offset_hours = when
    latitude, longitude = location
    zenith = -0.01454389765 # official
    # zenith = -0.10452846326 # civil

    # The day of the year
    n1 = floor(275 * month / 9)
    n2 = floor((month + 9) / 12)
    n3 = (1 + floor((year - 4 * floor(year / 4) + 2) / 3))
    n = n1 - (n2 * n3) + day - 30

    # The longitude to hour value and an approximate time
    lng_hour = longitude / 15
    t_rise = n + ((6 - lng_hour) / 24)
    t_set = n + ((18 - lng_hour) / 24)

    # The Sun's mean anomaly
    m_rise = (0.9856 * t_rise) - 3.289
    m_set = (0.9856 * t_set) - 3.289

    # The Sun's true longitude
    l_rise = rev360(m_rise + (1.916 * sin(m_rise * pi / 180)) + (0.020 * sin(2 * m_rise * pi / 180)) + 282.634)
    l_set = rev360(m_set + (1.916 * sin(m_set * pi / 180)) + (0.020 * sin(2 * m_set * pi / 180)) + 282.634)

    # The Sun's right ascension
    ra_rise = degrees(atan(0.91764 * tan(l_rise * pi / 180)))
    ra_set = degrees(atan(0.91764 * tan(l_set * pi / 180)))

    # Ascension value needs to be in the same quadrant as l_rise or l_set
    l_quadrant_rise  = (floor(l_rise / 90)) * 90
    l_quadrant_set  = (floor(l_set / 90)) * 90
    ra_quadrant_rise = (floor(ra_rise / 90)) * 90
    ra_quadrant_set = (floor(ra_set / 90)) * 90
    ra_rise += l_quadrant_rise - ra_quadrant_rise
    ra_set += l_quadrant_set - ra_quadrant_set

    # Ascension value needs to be converted into hours
    ra_rise /= 15
    ra_set /= 15

    # The Sun's declination
    sin_dec_rise = 0.39782 * sin(l_rise * pi / 180)
    sin_dec_set = 0.39782 * sin(l_set * pi / 180)
    cos_dec_rise = cos(asin(sin_dec_rise))
    cos_dec_set = cos(asin(sin_dec_set))

    # The Sun's local hour angle
    cos_h_rise = (zenith - (sin_dec_rise * sin(latitude * pi / 180))) / (cos_dec_rise * cos(latitude * pi / 180))
    cos_h_set = (zenith - (sin_dec_set * sin(latitude * pi / 180))) / (cos_dec_set * cos(latitude * pi / 180))

    if cos_h_rise > 1:    cos_h_rise = cos_h_rise - 1
    elif cos_h_rise < -1: cos_h_rise = cos_h_rise + 1
    if cos_h_set > 1:     cos_h_set = cos_h_set - 1
    elif cos_h_set < -1:  cos_h_set = cos_h_set + 1
    
    # h_rise or h_set and convert into hours
    h_rise = (360 - degrees(acos(cos_h_rise))) / 15
    h_set = (degrees(acos(cos_h_set))) / 15

    # Local mean time of rising/setting
    tB_rise = h_rise + ra_rise - (0.06571 * t_rise) - 6.622
    tB_set = h_set + ra_set - (0.06571 * t_set) - 6.622

    # Adjust back to UTC
    ut_rise = rev24(tB_rise - lng_hour)
    ut_set = rev24(tB_set - lng_hour)

    # Convert UT value to local time zone of latitude/longitude
    local_t_rise = rev24(ut_rise + tz_offset_hours)
    local_t_set = rev24(ut_set + tz_offset_hours)

    # Return sunrise and sunset
    return local_t_rise, local_t_set

def into_range(x, range_min, range_max):
    shiftedx = x - range_min
    delta = range_max - range_min
    return (((shiftedx % delta) + delta) % delta) + range_min

def dms(n):
    mnt, sec = divmod(abs(n) * 3600, 60)
    deg, mnt = divmod(mnt, 60)
    if n < 0:
        deg *= -1
    return int(deg), int(mnt), sec


def rev360(n):
    return  n - floor(n / 360) * 360

def rev24(n):
    return  n - floor(n / 24) * 24

def current_time_data():

    time_data = dt.now()
    year = time_data.year
    month = time_data.month
    day = time_data.day
    hour = time_data.hour
    minute = time_data.minute
    second = time_data.second
    tz_offset_hours = int((time.timezone if (time.localtime().tm_isdst == 0) else time.altzone) / 60 / 60 * -1)

    return year, month, day, hour, minute, second, tz_offset_hours, time_data

if __name__ == '__main__':
    updated_at = None
    seconds_per_minute = 60
    update_interval_minutes = 15
    update_interval_seconds = seconds_per_minute * update_interval_minutes

    while True:
        # Date and location information
        year, month, day, hour, minute, second, tz_offset_hours, now = current_time_data()

        if not updated_at or (now - updated_at).seconds >= update_interval_seconds:
            with open(os.path.relpath('config.json')) as json_file:
                config_file = json.load(json_file)
                latitude = float(config_file['latitude'])
                longitude = float(config_file['longitude'])

            # Get the Sun's apparent location in the sky
            azimuth, elevation = sunpos((year, month, day, hour, minute, second, tz_offset_hours), (latitude, longitude), True)

            # Degree convert to degree, minute, second
            azimuth_degree, azimuth_minute, azimuth_second = dms(azimuth)
            elevation_degree, elevation_minute, elevation_second = dms(elevation)
            latitude_degree, latitude_minute, latitude_second = dms(latitude)
            longitude_degree, longitude_minute, longitude_second = dms(longitude)

            # Get sunrise and sunset time
            sunrise, sunset = suninfo((year, month, day, tz_offset_hours), (latitude, longitude))

            # Degree convert to degree, minute, second
            sunrise_hour, sunrise_minute, sunrise_second = dms(sunrise)
            sunset_hour, sunset_minute, sunset_second = dms(sunset)

            # Get current time zone
            tz = datetime.timezone(datetime.timedelta(hours=tz_offset_hours))

            sunrise_str = f"{sunrise_hour}:{sunrise_minute}"
            sunset_str = f"{sunset_hour}:{sunset_minute}"
            midnight_str = "0:0"
            format_str = "%H:%M"
            now_datetime = datetime.datetime.strptime(f"{now.hour}:{now.minute}", format_str)
            sunrise_datetime = datetime.datetime.strptime(sunrise_str, format_str)
            sunset_datetime = datetime.datetime.strptime(sunset_str, format_str)
            midnight_datetime = datetime.datetime.strptime(midnight_str, format_str)

            midnight_to_sunrise_delta_seconds = (sunrise_datetime - midnight_datetime).total_seconds()
            sunrise_to_sunset_delta_seconds = (sunset_datetime - sunrise_datetime).total_seconds()
            midnight_to_now_delta_seconds = (now_datetime - midnight_datetime).total_seconds()

            midnight_to_now = midnight_to_now_delta_seconds / 84600
            midnight_to_sunrise = midnight_to_sunrise_delta_seconds / 84600
            sunrise_to_sunset = sunrise_to_sunset_delta_seconds / 84600
            sunset_to_midnight = (84600 - (midnight_to_sunrise_delta_seconds + sunrise_to_sunset_delta_seconds)) / 84600

            midnight_to_now_units = int(round(midnight_to_now * 96, 0))
            midnight_to_sunrise_units = int(round(midnight_to_sunrise * 96, 0))
            sunrise_to_sunset_units = int(round(sunrise_to_sunset * 96, 0))
            sunset_to_midnight_units = int(round(sunset_to_midnight * 96))

            midnight_to_sunrise_formatted = ["="] * midnight_to_sunrise_units
            sunrise_to_sunset_formatted = ["-"] * sunrise_to_sunset_units
            sunset_to_midnight_formatted = ["="] * sunset_to_midnight_units
            concatenated = midnight_to_sunrise_formatted + sunrise_to_sunset_formatted + sunset_to_midnight_formatted
            concatenated.insert(midnight_to_now_units, "*")
            del concatenated[midnight_to_now_units + 1]
            print("".join(concatenated))

            # Output the results
            if sys.argv[-1] == "--debug":
                print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
                print(f'When: {"0" if (day < 10) else ""}{day}.{"0" if (month < 10) else ""}{month}.{year} {"0" if (hour < 10) else ""}{hour}:{"0" if (minute < 10) else ""}{minute}:{"0" if (second < 10) else ""}{int(second)} UTC{"+" if (tz_offset_hours > 0) else ""}{tz_offset_hours}')
                print(f"Where: Latitude = {latitude_degree}° {latitude_minute}' "+f'{int(latitude_second)}", Longitude = {longitude_degree}° '+f"{longitude_minute}' "+f'{int(longitude_second)}"')
                print(f"Azimuth: {azimuth_degree}° {azimuth_minute}' "+f'{int(azimuth_second)}" or {round(azimuth, 4)}')
                print(f"Elevation: {elevation_degree}° {elevation_minute}' "+f'{int(elevation_second)}" or {round(elevation, 4)}')
                print(f'Sunrise = {str(0)+str(sunrise_hour) if sunrise_hour//10 == 0 else sunrise_hour}:{str(0)+str(sunrise_minute) if sunrise_minute//10 == 0 else sunrise_minute}:{str(0)+str(int(sunrise_second)) if sunrise_second//10 == 0 else int(sunrise_second)}, Sunset = {str(0)+str(sunset_hour) if sunset_hour//10 == 0 else sunset_hour}:{str(0)+str(sunset_minute) if sunset_minute//10 == 0 else sunset_minute}:{str(0)+str(int(sunset_second)) if sunset_second//10 == 0 else int(sunset_second)}')
            updated_at = datetime.datetime.now()
