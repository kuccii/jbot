from job_bot.discovery.providers.greenhouse import GreenhouseProvider
from job_bot.discovery.providers.lever import LeverProvider
from job_bot.discovery.providers.ashby import AshbyProvider

ATS_PROVIDERS = [
    GreenhouseProvider(),
    LeverProvider(),
    AshbyProvider(),
]
