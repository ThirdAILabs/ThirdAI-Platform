#!/bin/bash

function styled_message() {
    local message="$1"
    local color="$2"

    if [ "$color" == "31" ]; then
        # For Error
        echo -e "\e[1;31m====================================================\e[0m"
        echo -e "\e[1;31m               ${message}             \e[0m"
        echo -e "\e[1;31m====================================================\e[0m"
    else
        echo -e "\n\e[1;${color}m======= ${message}\e[0m\n"
    fi
}


function install_ansible() {
    # Check if ansible-playbook is installed
    if ! command -v ansible-playbook &> /dev/null; then
        styled_message "Ansible not found, installing...", "32"

        # Install Ansible based on the OS
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            if [ -f /etc/debian_version ]; then
                echo "Installing Ansible on Ubuntu/Debian..."
                sudo apt update
                sudo apt install -y software-properties-common
                sudo add-apt-repository --yes --update ppa:ansible/ansible
                sudo apt install -y ansible
            elif [ -f /etc/system-release ] && grep -q "Amazon Linux release 2023" /etc/system-release; then
                echo "Installing Ansible on CentOS/RHEL..."
                sudo dnf install -y ansible
            elif [ -f /etc/system-release ] && grep -q "Amazon Linux release 2" /etc/system-release; then
                echo "Installing Ansible on Amazon Linux 2..."
                sudo amazon-linux-extras install -y ansible2
            else
                styled_message "Unsupported OS: $OSTYPE", "31"
                styled_message "Please download and install Ansible manually for your operating system.", "31"
                exit 1
            fi
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            echo "Installing Ansible on macOS..."
            brew install ansible
        else
            styled_message "Unsupported OS: $OSTYPE", "31"
            styled_message "Please download and install Ansible manually for your operating system." "31"
            exit 1
        fi
    else
        styled_message "Ansible is already installed" "32"
    fi

    echo "Installing required Ansible Galaxy collections..."
    ansible-galaxy collection install community.general
    ansible-galaxy collection install ansible.posix
    # From v4.0.0 commuinty docker support is not there for amazon linux 2
    if [ -f /etc/system-release ] && grep -q "Amazon Linux release 2" /etc/system-release; then
        ansible-galaxy collection install community.docker:==3.13.1 --force
    else
        ansible-galaxy collection install community.docker
    fi
    ansible-galaxy collection install community.postgresql

    styled_message "All required Ansible Galaxy collections are installed." "32"
}


VERBOSE=0  # Default: No verbose mode
CLEANUP=0  # Flag for cleanup mode
ONBOARD_CLIENTS=0  # Flag for onboard_clients mode
NEW_CLIENT_CONFIG_PATH=""   # Declare globally, default empty
aws_secret_name=""
    
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -v|--verbose) VERBOSE=1 ;;   # Enable verbose mode if -v or --verbose is passed
        --cleanup) CLEANUP=1 ;;  # Enable cleanup mode if --cleanup is passed
        --onboard_clients) ONBOARD_CLIENTS=1 ;;  # Enable onboard_clients if --onboard_clients is passed
        --aws_secret_name) 
            if [[ -z "$2" || "$2" == -* ]]; then
                styled_message "Error: AWS secret name cannot be empty" "31" >&2
                exit 1
            fi
            aws_secret_name="$2"
            shift ;;     
        *) CONFIG_PATH="$1" ;;
    esac
    shift
done


# Check if config file is provided and conflicting arguments are not provided
if [ -z "$CONFIG_PATH" ] || { [ "$ONBOARD_CLIENTS" -eq 1 ] && [ "$CLEANUP" -eq 1 ]; }; then
    styled_message "Usage: $0 [-v|--verbose] [--cleanup] [--aws_secret_name <secret-name>] /path/to/your/config.yml" "31"
    exit 1
fi

# Check if config file exists
if [ ! -f "$CONFIG_PATH" ]; then
    styled_message "Config file not found at $CONFIG_PATH" "31"
    exit 1
fi

install_ansible

styled_message "Using config file at $CONFIG_PATH" "32"

EXTRA_VARS="config_path=$CONFIG_PATH"

if [ "$ONBOARD_CLIENTS" -eq 1 ] || [ "$CLEANUP" -eq 1 ]; then
    # SKIP: No need of these credentials in case of 'ON-BOARDING CLIENTS' or 'CLEANUP'
    :
elif [ ! -z "$aws_secret_name" ]; then
    if [ -f /etc/system-release ] && grep -qE "^Amazon Linux release 2(\s*\(.*\))?$" /etc/system-release; then
        styled_message "Amazon Linux 2 doesn't support ansible with aws secret lookup feature currently." "31"
        exit 1
    fi
    # Information user aws needs to be configured
    styled_message "INFO: Assuming that AWS CLI is configured" "33"
    sleep 5
    EXTRA_VARS+=" aws_secret_name=$aws_secret_name"
fi

if [ "$ONBOARD_CLIENTS" -eq 1 ]; then
    read -p "Enter the absolute path to the new client config file (e.g., /path/to/new_client_config.yml): " NEW_CLIENT_CONFIG_PATH

    # Check if a valid path was provided
    if [ -z "$NEW_CLIENT_CONFIG_PATH" ]; then
        styled_message "Error: No file location provided for new client configuration." "31"
        exit 1
    fi

    # Check if config file exists
    if [ ! -f "$NEW_CLIENT_CONFIG_PATH" ]; then
        styled_message "New client config file not found at $NEW_CLIENT_CONFIG_PATH" "31"
        exit 1
    fi

    styled_message "Using new client config file at $NEW_CLIENT_CONFIG_PATH" "32"
    EXTRA_VARS+=" new_client_config_path=$NEW_CLIENT_CONFIG_PATH"
fi

# Model path
MODEL_FOLDER="pretrained-models/"

# Warn if model file is not found
if [ "$CLEANUP" -ne 1  ]; then
    if [ ! -d "$MODEL_FOLDER" ]; then
        styled_message "WARNING: Model file not found at $GENERATIVE_MODEL_FOLDER. The playbook will proceed without it." "33"
        sleep 5
    else
        # pretrained model_folder location
        EXTRA_VARS+=" model_folder=$(realpath "$MODEL_FOLDER")"
    fi

    # Search for docker_images folder with a prefix
    DOCKER_IMAGES_PATH=$(find . -type d -name "docker_images-*" | head -n 1)
    if [ -z "$DOCKER_IMAGES_PATH" ]; then
        styled_message "WARNING: No docker_images folder found with prefix 'docker_images-'. The playbook will proceed without it." "33"
        sleep 5
    else
        DOCKER_IMAGES_PATH=$(realpath "$DOCKER_IMAGES_PATH")
        styled_message "Found docker images folder at $DOCKER_IMAGES_PATH" "32"
        EXTRA_VARS+=" docker_images=$(realpath "$DOCKER_IMAGES_PATH")"
    fi
fi

# Change directory to platform directory
cd "$(dirname "$0")/platform" || exit 1

# Run the appropriate playbook based on the cleanup flag
if [ "$CLEANUP" -eq 1 ]; then
    styled_message "Running cleanup playbook..." "32"
    if [ "$VERBOSE" -eq 1 ]; then
        ansible-playbook playbooks/test_cleanup.yml --extra-vars "$EXTRA_VARS" -vvvv
    else
        ansible-playbook playbooks/test_cleanup.yml --extra-vars "$EXTRA_VARS"
    fi
elif [ "$ONBOARD_CLIENTS" -eq 1 ]; then
    styled_message "Running onboarding playbook..." "32"
    if [ "$VERBOSE" -eq 1 ]; then
        ansible-playbook playbooks/onboard_clients.yml --extra-vars "$EXTRA_VARS" -vvvv
    else
        ansible-playbook playbooks/onboard_clients.yml --extra-vars "$EXTRA_VARS"
    fi
else
    styled_message "Running deployment playbook..." "32"
    if [ "$VERBOSE" -eq 1 ]; then
        ansible-playbook playbooks/test_deploy.yml --extra-vars "$EXTRA_VARS" -vvvv
    else
        ansible-playbook playbooks/test_deploy.yml --extra-vars "$EXTRA_VARS"
    fi
fi