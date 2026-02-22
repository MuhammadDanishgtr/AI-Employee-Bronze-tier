FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir watchdog>=4.0.0

# Copy source code and vault structure
COPY watchers/ ./watchers/
COPY AI_Employee_Vault/ ./AI_Employee_Vault/

# Create required vault folders
RUN mkdir -p AI_Employee_Vault/Drop_Folder \
             AI_Employee_Vault/Needs_Action \
             AI_Employee_Vault/Logs \
             AI_Employee_Vault/Done \
             AI_Employee_Vault/Inbox \
             AI_Employee_Vault/Plans \
             AI_Employee_Vault/Pending_Approval \
             AI_Employee_Vault/Approved \
             AI_Employee_Vault/Rejected \
             AI_Employee_Vault/Briefings

# Vault and drop folder as volumes so host can interact
VOLUME ["/app/AI_Employee_Vault"]

ENV VAULT_PATH=/app/AI_Employee_Vault
ENV DROP_FOLDER=/app/AI_Employee_Vault/Drop_Folder
ENV CHECK_INTERVAL=10

CMD ["python", "watchers/filesystem_watcher.py", \
     "--vault", "/app/AI_Employee_Vault", \
     "--drop", "/app/AI_Employee_Vault/Drop_Folder", \
     "--interval", "10"]
