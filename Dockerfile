FROM python:3.13-slim

WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libexpat1 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies (Gold Tier)
COPY pyproject.toml .
RUN pip install --no-cache-dir \
    "watchdog>=4.0.0" \
    "google-auth>=2.0.0" \
    "google-auth-oauthlib>=1.0.0" \
    "google-api-python-client>=2.0.0" \
    "apscheduler>=3.10.0" \
    "playwright>=1.40.0" \
    "python-dotenv>=1.0.0" \
    "mcp>=1.0.0" \
    "tweepy>=4.14.0" \
    "tenacity>=8.2.0" \
    "requests>=2.31.0" \
    "requests-oauthlib>=1.3.0"

# Install Playwright Chromium browser
RUN playwright install chromium

# Copy source code
COPY watchers/ ./watchers/
COPY mcp_servers/ ./mcp_servers/
COPY AI_Employee_Vault/ ./AI_Employee_Vault/

# Create required vault folders and credentials directory
RUN mkdir -p AI_Employee_Vault/Drop_Folder \
             AI_Employee_Vault/Needs_Action \
             AI_Employee_Vault/Logs \
             AI_Employee_Vault/Done \
             AI_Employee_Vault/Inbox \
             AI_Employee_Vault/Plans \
             AI_Employee_Vault/Pending_Approval \
             AI_Employee_Vault/Approved \
             AI_Employee_Vault/Rejected \
             AI_Employee_Vault/Briefings \
             AI_Employee_Vault/Audits/Weekly \
             AI_Employee_Vault/Error_Queue \
             AI_Employee_Vault/Business_Domain \
             credentials

# Vault as volume so host can interact with files
VOLUME ["/app/AI_Employee_Vault"]
# Credentials volume for OAuth tokens (never commit to image)
VOLUME ["/app/credentials"]

# Environment defaults (override via docker run -e or .env mount)
ENV VAULT_PATH=/app/AI_Employee_Vault
ENV DROP_FOLDER_PATH=/app/AI_Employee_Vault/Drop_Folder
ENV GMAIL_CREDENTIALS_PATH=/app/credentials/gmail_credentials.json
ENV GMAIL_TOKEN_PATH=/app/credentials/gmail_token.json
ENV LINKEDIN_SESSION_PATH=/app/credentials/linkedin_session
ENV SCHEDULE_GMAIL_INTERVAL=120
ENV SCHEDULE_LINKEDIN_INTERVAL=900
ENV SCHEDULE_DASHBOARD_INTERVAL=600
ENV SCHEDULE_ODOO_INTERVAL=3600
ENV SCHEDULE_FACEBOOK_INTERVAL=600
ENV SCHEDULE_TWITTER_INTERVAL=600
ENV SCHEDULE_ERROR_RECOVERY_INTERVAL=1800
ENV AUDIT_SCHEDULE_DAY=mon
ENV AUDIT_SCHEDULE_HOUR=8
ENV CHECK_INTERVAL=10

# Run the Gold Tier orchestrator (manages all 8 scheduled jobs)
CMD ["python", "watchers/orchestrator.py", \
     "--vault", "/app/AI_Employee_Vault", \
     "--drop", "/app/AI_Employee_Vault/Drop_Folder"]
