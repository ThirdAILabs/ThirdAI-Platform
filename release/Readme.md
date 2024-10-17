# Docker Image Builder and Pusher

This project automates the process of building, tagging, and pushing Docker images to Azure Container Registry for various branches of a project. It is designed to be extensible, allowing for easy integration with other cloud providers.

## Project Overview

The main components of this project are:

- **AzureProvider**: Handles interactions with Azure Container Registry.
- **CloudProviderInterface**: Defines the interface for cloud provider operations.
- **ImageNames**: Manages the naming conventions for Docker images.
- **Main Script**: Orchestrates the building and pushing of Docker images based on configurations and command-line arguments.
- **Utils**: Provides utility functions and data models.

## Files

### `azure_provider.py`

This module implements the `AzureProvider` class, which handles building, pushing, and managing Docker images in Azure Container Registry.

#### Key Methods:

- `build_image`: Builds a Docker image.
- `push_image`: Pushes a Docker image to the registry.
- `get_image_digest`: Retrieves the digest of an image.
- `delete_image`: Deletes an image tag from the registry.
- `create_credentials`: Creates credentials for accessing the registry.
- `update_credentials`: Updates existing credentials.
- `update_image`: Updates an image with a new name and tag.
- `get_registry_name`: Returns the registry name.
- `get_full_image_name`: Constructs the full image name including the tag.

### `cloud_provider_interface.py`

Defines the `CloudProviderInterface` class, an abstract base class that outlines the methods required for a cloud provider interface.

#### Key Methods:

- `authorize_credentials`: Authorizes credentials for the provider.
- `build_image`: Abstract method to build an image.
- `push_image`: Abstract method to push an image.
- `get_image_digest`: Abstract method to get the image digest.
- `delete_image`: Abstract method to delete an image.
- `create_credentials`: Abstract method to create credentials.
- `update_credentials`: Abstract method to update credentials.
- `update_image`: Abstract method to update an image.
- `get_registry_name`: Abstract method to get the registry name.
- `get_full_image_name`: Abstract method to get the full image name.
- `get_local_image_digest`: Gets the digest of a locally built image.

### `docker_constants.py`

Manages the naming conventions for Docker images used in the project.

### `push.py`

The main script that orchestrates the building and pushing of Docker images.

#### Key Functions:

- `get_args`: Parses command-line arguments.
- `get_tag`: Gets the version tag for a specific branch.
- `get_root_absolute_path`: Gets the absolute path to the project root.
- `build_image`: Builds a Docker image.
- `build_images`: Builds all Docker images.
- `verify_tag`: Verifies that the image tag matches the checksum.
- `push_images`: Pushes Docker images to the registry.
- `load_config`: Loads the YAML configuration file.
- `save_config`: Saves the configuration dictionary to a YAML file.
- `main`: Main function to build and push Docker images.

### `utils.py`

Provides utility functions and data models.

#### Key Functions and Classes:

- `image_name_for_branch`: Generates the image name for a given branch.
- `Credentials`: Pydantic model to store credentials for Docker registry access.

## Configuration

### `config.yaml`

The `config.yaml` file is used to configure the settings for building and pushing Docker images. Below is a detailed explanation of its structure and contents.

#### Example `config.yaml`

```yaml
provider: azure
azure:
  registry: thirdaiplatform.azurecr.io
  branches:
    prod:
      version: "1.0.0"
      push_credentials:
        username: your_push_username
        password: your_push_password
      pull_credentials:
        username: your_pull_username
        password: your_pull_password
    test:
      version: "0.0.1"
      push_credentials:
        username: your_push_username
        password: your_push_password
      pull_credentials:
        username: your_pull_username
        password: your_pull_password
```

### Fields
- provider: The cloud provider to use. Currently supported: azure.
- azure: Configuration specific to Azure Container Registry.
    - registry: The URL of the Azure Container Registry.
    - branches: A dictionary of branch-specific configurations.
        - <branch_name>: The name of the branch (e.g., prod, test).
            - version: The version tag for the branch.
            - push_credentials: Credentials for pushing images.
                - username: The username for pushing images.
                - password: The password for pushing images.
            - pull_credentials: Credentials for pulling images.
                - username: The username for pulling images.
                - password: The password for pulling images.


#### If Configuration is Missing

If the configuration file or any of its fields are missing, the script will populate it with default values during execution. For example, if the `branches` section is missing, it will be created with a default version and empty credentials.

### Populating `config.yaml`

1. **Load Configuration**: The script first tries to load the existing `config.yaml` file.
2. **Populate Missing Fields**: If any fields are missing, the script will populate them with default values.
3. **Save Configuration**: The updated configuration is saved back to the `config.yaml` file.

## Switching to Another Cloud Provider

To switch to another cloud provider, follow these steps:

1. **Implement the Provider Class**: Create a new provider class that implements the `CloudProviderInterface`. This class should handle the specific interactions with the new cloud provider.
2. **Update Configuration**: Modify the `config.yaml` file to include settings for the new provider.
3. **Modify the Main Script**: Update the `main.py` script to instantiate and use the new provider class based on the configuration.

### Example

#### Implementing `GCPProvider`

```python
from cloud_provider_interface import CloudProviderInterface

class GCPProvider(CloudProviderInterface):
    # Implement all required methods
    ...

```

#### Updating ``config.yaml``

```yaml
provider: gcp
gcp:
  registry: your_gcp_registry
  branches:
    prod:
      version: "1.0.0"
      push_credentials:
        username: your_push_username
        password: your_push_password
      pull_credentials:
        username: your_pull_username
        password: your_pull_password
```

#### Modifying ``push.py``
```python

def main() -> None:
    ...
    provider_name = config["provider"]
    if provider_name == "azure":
        provider = AzureProvider(...)
    elif provider_name == "gcp":
        provider = GCPProvider(...)
    ...
```


## Usage

### Command-line Arguments

- `-b, --branch`: The branch to push Docker images to. (Required)
- `--config`: Path to the YAML configuration file. Defaults to `config.yaml`.
- `--no-cache`: If present, Docker will not use cache when building images.
- `--version`: Version to use for the provided branch, if not it will take the one from config.
- `--dont-update-latest`: If present, the 'latest' tag will not be updated.

### Example Command

```sh
python push.py --branch test --config config.yaml --version 1.0.0
