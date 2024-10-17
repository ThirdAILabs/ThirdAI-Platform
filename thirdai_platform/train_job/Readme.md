# Train Job

This repository contains the implementation of a machine learning model interface and several concrete models using ThirdAI's Models. The models are designed to handle both unsupervised and supervised training, including sharded training for large datasets.


- **`Dockerfile`**: Dockerfile to build the Docker image for running the training job.
- **`models/`**: Directory containing the model implementations.
- **`reporter.py`**: Provides the `Reporter` class for logging training progress and status to an external API.
- **`run.py`**: Entry point script to run the training job.
- **`utils.py`**: Contains utility functions for processing files and handling training data.
- **`variables.py`**: Defines various configuration classes used to load environment variables for model training.