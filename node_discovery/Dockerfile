# Use the official image of Python 3.9
FROM python:3.9

# Set the working directory in the container to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install dependencies from requirements.txt
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Run the application
CMD ["python3", "run.py"]