# Step 71: Define the simulation-owned environmental state.
class EnvironmentState:
    """Deterministic environmental conditions owned by the simulation world."""

    SEASONS = ("spring", "summer", "autumn", "winter")
    WEATHER_TYPES = ("clear", "cloudy", "rain", "snow")

    def __init__(
        self,
        temperature=20.0,
        precipitation=0.0,
        wind_speed=0.0,
        season="spring",
        weather="clear",
        day=1,
    ):
        if season not in self.SEASONS:
            raise ValueError("Invalid season.")
        if weather not in self.WEATHER_TYPES:
            raise ValueError("Invalid weather.")
        if precipitation < 0:
            raise ValueError("Precipitation cannot be negative.")
        if wind_speed < 0:
            raise ValueError("Wind speed cannot be negative.")
        if day < 1:
            raise ValueError("Day must be greater than zero.")

        self.temperature = float(temperature)
        self.precipitation = float(precipitation)
        self.wind_speed = float(wind_speed)
        self.season = season
        self.weather = weather
        self.day = int(day)

    # Step 71: Return a stable environmental snapshot.
    def to_dict(self):
        return {
            "temperature": self.temperature,
            "precipitation": self.precipitation,
            "wind_speed": self.wind_speed,
            "season": self.season,
            "weather": self.weather,
            "day": self.day,
        }

    # Step 72: Advance environmental conditions deterministically.
    def advance_tick(self):
        self.day += 1

        season_index = ((self.day - 1) // 90) % len(self.SEASONS)
        self.season = self.SEASONS[season_index]

        weather_index = (self.day - 1) % len(self.WEATHER_TYPES)
        self.weather = self.WEATHER_TYPES[weather_index]

        seasonal_temperatures = {
            "spring": 15.0,
            "summer": 25.0,
            "autumn": 12.0,
            "winter": 0.0,
        }

        self.temperature = seasonal_temperatures[self.season]

        precipitation_by_weather = {
            "clear": 0.0,
            "cloudy": 0.2,
            "rain": 1.0,
            "snow": 0.8,
        }

        wind_by_weather = {
            "clear": 2.0,
            "cloudy": 4.0,
            "rain": 7.0,
            "snow": 5.0,
        }

        self.precipitation = precipitation_by_weather[self.weather]
        self.wind_speed = wind_by_weather[self.weather]

    def get_condition(self, condition_name):
        if condition_name not in self.to_dict():
            raise ValueError(f"Unknown environmental condition: {condition_name}.")
        return self.to_dict()[condition_name]
