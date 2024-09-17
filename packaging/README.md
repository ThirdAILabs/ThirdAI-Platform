# ThirdAI Platform Driver Script

This repository contains a script, `driver.sh`, which automates the deployment of the ThirdAI platform using Ansible. This document provides instructions on how to use the script and what it does.

## Prerequisites

Before running the script, ensure the following are installed on your machine:

1. **Ansible**: The script automatically installs Ansible if it's not already installed.
2. **Bash**: Ensure you have a Bash shell environment available to run the script.
3. **Configuration File**: A `config.yml` file is required to provide necessary configurations for the Ansible playbooks.

## Files in the Package

- `driver.sh`: The main script to automate the deployment.
- `config.yml`: The configuration file required for Ansible to deploy the platform.
- `models/qwen2-0_5b-instruct-fp16.gguf`: The generation model used by the platform.
- `platform`: This contain Ansible playbooks and other necessary files.

## How to Run `driver.sh`

### Step-by-Step Instructions

1. **Download and Extract the Package**:
   
   After downloading the `thirdai-platform-package.tar.gz`, extract it:

   ```bash
   mkdir -p my_folder
   tar -xzvf thirdai-platform-package.tar.gz -C my_folder
   ```

   This will extract the following files and directories:
   - `driver.sh`
   - `config.yml`
   - `platform/`
   - `models/qwen2-0_5b-instruct-fp16.gguf`

2. **Make the `driver.sh` Script Executable**:
   
   Before running the script, ensure that it has executable permissions. If not, change the permissions by running:

   ```bash
   chmod +x driver.sh
   ```

3. **Run the Script**:
   
   The `driver.sh` script requires the path to a `config.yml` file as an argument. You can use the default `config.yml` provided in the package or supply your own configuration file.

   To run the script with the default configuration:

   ```bash
   ./driver.sh ./config.yml
   ```

4. **What Happens During Execution**:
   
   - The script checks for the installation of Ansible. If Ansible is not installed, the script will install it automatically.
   - The script verifies if the model file (`qwen2-0_5b-instruct-fp16.gguf`) is present in the `models/` directory. If the file is not found, the script issues a warning but proceeds with the playbook execution.
   - The script then navigates to the `platform/` directory and runs the `test_deploy.yml` Ansible playbook using the provided `config.yml` and the model path as extra variables.

### Troubleshooting

- **Permission Denied**: If you encounter a "permission denied" error while running the script, ensure that the script has executable permissions by running the `chmod +x driver.sh` command. If you are using a `.pem` key for SSH, make sure the key file's permission is set to `400` by running `chmod 400 your-key.pem`.
- **Config File Not Found**: Ensure that the path to the `config.yml` file is correct and that the file exists at the specified location.
- **Ansible Errors**: If Ansible encounters errors during execution, review the output carefully. Ensure that your system has internet access for package installation and model downloading.