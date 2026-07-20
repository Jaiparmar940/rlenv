# OpenReward (ORS) serving image for no-start-env.
# Serves the environment only — no provider SDKs, no eval harness.
FROM python:3.12-slim

WORKDIR /app

# Install the package + ORS adapter. inspect-ai is a core dependency of the
# package (the Inspect task lives beside the adapter); the adapter itself
# imports only nostart.* and openreward.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir ".[openreward]"

EXPOSE 8080

CMD ["python", "-m", "nostart.openreward.server"]
