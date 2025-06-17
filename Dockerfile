FROM python:3.11

WORKDIR /app

RUN apt-get update && apt-get install -y bash build-essential

# Copy your project (including adk.yaml) into the container
COPY . /app/credit-risk-agent

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r credit-risk-agent/requirements.txt

EXPOSE 8080

# Set working dir where adk.yaml is located
WORKDIR /app

# Run the agent using adk.yaml
CMD ["adk", "web", "--host", "0.0.0.0", "--port", "8080"]
