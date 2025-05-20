# Use an official Python runtime as a parent image
FROM python:slim

# Set the working directory in the container
WORKDIR /card-game-assistant

# Copy only necessary files and directories into the container
COPY requirements.txt /card-game-assistant/
COPY run.py /card-game-assistant/
COPY config.py /card-game-assistant/
COPY templates/ /card-game-assistant/templates/
COPY static/ /card-game-assistant/static/
COPY app/ /card-game-assistant/app
# Add other necessary files and directories here

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Define environment variable
ENV FLASK_APP=run.py
ENV FLASK_ENV=development

# Run app.py when the container launches
CMD ["flask", "run", "--host=0.0.0.0"]
