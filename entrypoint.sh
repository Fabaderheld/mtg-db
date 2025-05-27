#!/bin/bash
cp -r /card-game-assistant/core_static/* /card-game-assistant/static

# Start the Flask application
flask run --host=0.0.0.0