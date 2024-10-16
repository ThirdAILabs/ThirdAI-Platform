# Project Structure Overview

This project is organized into several key directories and files, each serving a specific purpose. Below is an overview of these components and instructions on how to add new functionalities.

## Adding a New Router

To add a new router to the project, follow these steps:

1. **Create the Router**
   - In the `routers/` directory, create a new Python file for your router. Define your router and the necessary routes in this file.

2. **Define Models (if needed)**
   - If your router requires interaction with ThirdAI models and the required model does not exist, define a new model in the `models/` directory.

3. **Define Pydantic Models (if needed)**
   - If you need new data validation or serialization models, define them in the `pydantic_models/` directory.

4. **Include the Router in main.py**
   - Open `main.py` and include your new router. Import your router and add it to the application instance. Here is an example of how to do this:

   ```python
   from fastapi import FastAPI
   from deployment_job.routers import your_new_router

   app = FastAPI()

   # Include your new router
   app.include_router(your_new_router.router)
