# Use the official FastAPI image with Python 3.11
FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

# Set the working directory in the container to /app
WORKDIR /app

# Copy the requirements.txt file into the container
COPY requirements.txt /app/

# Install dependencies from requirements.txt
RUN python3 -m pip install --no-cache-dir -r requirements.txt
RUN python3 -m pip install pdftitle

# Copy the current directory contents into the container at /app
COPY . /app

# Set the default command to run the FastAPI application
CMD ["python3", "run.py"]