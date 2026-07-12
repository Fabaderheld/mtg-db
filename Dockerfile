# Use an official Python runtime as a parent image
FROM python:slim

# Set the working directory in the container
WORKDIR /card-game-assistant

# Copy requirements first
COPY requirements.txt /card-game-assistant/

# Install dependencies immediately after copying requirements
RUN pip install --no-cache-dir -r requirements.txt

# Create directories
RUN mkdir /card-game-assistant/core_static /card-game-assistant/static

# Now copy application files
COPY run.py /card-game-assistant/
COPY config.py /card-game-assistant/
COPY templates/ /card-game-assistant/templates/
COPY static/css /card-game-assistant/core_static/css
COPY static/js /card-game-assistant/core_static/js
COPY static/fonts /card-game-assistant/core_static/fonts
COPY static/images /card-game-assistant/core_static/images
COPY app/ /card-game-assistant/app

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