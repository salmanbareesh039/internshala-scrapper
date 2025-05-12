# Use Apify's Python base image
FROM apify/actor-python:3.10

# Copy all files to the working directory
COPY . ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium and Chromedriver
RUN apt-get update && \
    apt-get install -y chromium-driver chromium-browser

# Set the default command to run your Python script
CMD ["python", "main.py"]
