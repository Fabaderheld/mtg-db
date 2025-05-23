# Use an official Python runtime as a parent image
FROM python:slim

# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 tesseract-ocr && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /card-game-assistant

# Copy only necessary files and directories into the container
COPY requirements.txt /card-game-assistant/
COPY run.py /card-game-assistant/
COPY config.py /card-game-assistant/
COPY templates/ /card-game-assistant/templates/

# Create a directory for core static files
RUN mkdir /card-game-assistant/core_static /card-game-assistant/static

# Copy static files into the container
COPY static/css /card-game-assistant/core_static/css
COPY static/js /card-game-assistant/core_static/js
COPY static/fonts /card-game-assistant/core_static/fonts
COPY static/images /card-game-assistant/core_static/images

COPY app/ /card-game-assistant/app
# Add other necessary files and directories here

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Define environment variable
ENV FLASK_APP=run.py
ENV FLASK_ENV=development

# Copy the entrypoint script into the container
COPY entrypoint.sh /card-game-assistant/entrypoint.sh

# Make entrypoint executable
RUN chmod +x entrypoint.sh

ENTRYPOINT ["/card-game-assistant/entrypoint.sh"]
