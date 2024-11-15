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
- `models/Llama-3.2-1B-Instruct-f16.gguf`: The generation model used by the platform.
- `platform`: This contains Ansible playbooks and other necessary files.

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
   - `models/Llama-3.2-1B-Instruct-f16.gguf`

2. **Make the `driver.sh` Script Executable**:
   
   Before running the script, ensure that it has executable permissions. If not, change the permissions by running:

   ```bash
   chmod +x driver.sh
   ```

3. **Specify Platform Image Branch (Optional)**:
   
   You can specify the `platform_image_branch` using the `--branch` or `-b` option. If you don’t provide this option, the script will default to using `release-test-main` and display a warning.

   ```bash
   ./driver.sh --branch your-branch-name ./config.yml
   ```

   If no branch is specified, the script will default to:

   ```bash
   WARNING: No platform_image_branch specified. Using default 'release-test-main'.
   ```

4. **Run the Script**:
   
   The `driver.sh` script requires the path to a `config.yml` file as an argument. You can use the default `config.yml` provided in the package or supply your own configuration file.

   To run the script with the default configuration and without specifying a branch:

   ```bash
   ./driver.sh ./config.yml
   ```
### Troubleshooting Steps for Changing Public IP on the Fly

When changing the public IP of your Keycloak instance, follow these steps to update the settings and ensure proper functionality:

---

5. **Steps to Update Frontend URL**

   - To access the admin console, follow these steps:

      1. **Set up Port Forwarding**  
         Open a terminal on your local machine and run the following command:  
         ```bash
         sudo ssh -i ~/Downloads/pratik-west-1.pem -L 443:<PRIVATE_IP_OF_MACHINE>:443 ubuntu@<NEW_PUBLIC_IP>
         ```  

      2. **Access the Admin Console**  
         Once port forwarding is successfully set up, open your browser on the local machine and navigate to:  
         ```  
         https://localhost/keycloak/admin/master/console/  
         ```  

         You should now be redirected to the admin console.

   - In the **Keycloak Admin Console**, go to:
      - Select the realm: `Thirdai-Platform`.
      - Navigate to **Realm Settings → General**.

   - Update the **Frontend URL** to:
     ```
     https://{newPublicIP}/keycloak
     ```
   - ⚠️ **Important**: Ensure the new public IP corresponds to the subdomain name specified for the SSL certificate.
   - If the subdomain does not match the new IP, you will need to provide an updated certificate for the new IP.
   - If you dont have the access to older admin console, then you may need to do change the env var `KC_HOSTNAME` and `KC_HOSTNAME_ADMIN` to new public IP in the Keycloak Job, restart it before seeing the change. 


6. **What Happens During Execution**:
   
   - The script checks for the installation of Ansible. If Ansible is not installed, the script will install it automatically.
   - The script verifies if the model folder (`gen-ai-models/`) is present. If the folder is not found, the script issues a warning but proceeds with the playbook execution.
   - The script searches for a `docker_images` folder and warns if it's not found, but proceeds with the playbook execution.
   - The script then navigates to the `platform/` directory and runs the `test_deploy.yml` Ansible playbook using the provided `config.yml`, the model path, the Docker images path, and the platform image branch as extra variables.

### Example Commands

#### Run the script with a specified branch:
```bash
./driver.sh --branch your-branch-name ./config.yml
```

#### Run the script without specifying a branch (will default to `release-test-main`):
```bash
./driver.sh ./config.yml
```

### Troubleshooting

- **Permission Denied**: If you encounter a "permission denied" error while running the script, ensure that the script has executable permissions by running the `chmod +x driver.sh` command. If you are using a `.pem` key for SSH, make sure the key file's permission is set to `400` by running `chmod 400 your-key.pem`.
- **Config File Not Found**: Ensure that the path to the `config.yml` file is correct and that the file exists at the specified location.
- **Ansible Errors**: If Ansible encounters errors during execution, review the output carefully. Ensure that your system has internet access for package installation and model downloading.