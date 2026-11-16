from job_hunter.config import load_config
c = load_config()
print(c.profile.name, c.profile.email, len(c.profile.skills))