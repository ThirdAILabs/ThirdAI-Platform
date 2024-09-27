#!/bin/bash

function install_ansible() {
    # Check if ansible-playbook is installed
    if ! command -v ansible-playbook &> /dev/null; then
        echo "Ansible not found, installing..."

        # Install Ansible based on the OS
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            if [ -f /etc/debian_version ]; then
                echo "Installing Ansible on Ubuntu/Debian..."
                sudo apt update
                sudo apt install -y software-properties-common
                sudo add-apt-repository --yes --update ppa:ansible/ansible
                sudo apt install -y ansible
            elif [ -f /etc/system-release ] && grep -q "Amazon Linux release 2" /etc/system-release; then
                echo "Installing Ansible on Amazon Linux 2..."
                sudo amazon-linux-extras install -y ansible2
            elif [ -f /etc/redhat-release ]; then
                echo "Installing Ansible on CentOS/RHEL..."
                sudo dnf install -y ansible
            else
                echo "Unsupported OS: $OSTYPE"
                echo "Please download and install Ansible manually for your operating system."
                exit 1
            fi
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            echo "Installing Ansible on macOS..."
            brew install ansible
        else
            echo "Unsupported OS: $OSTYPE"
            echo "Please download and install Ansible manually for your operating system."
            exit 1
        fi
    else
        echo "Ansible is already installed"
    fi

    echo "Installing required Ansible Galaxy collections..."
    ansible-galaxy collection install community.general
    ansible-galaxy collection install ansible.posix
    ansible-galaxy collection install community.docker

    echo "All required Ansible Galaxy collections are installed."
}

install_ansible

VERBOSE=0  # Default: No verbose mode
PLATFORM_IMAGE_BRANCH="release-test-main"  # Default value if not provided

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -v|--verbose) VERBOSE=1 ;;   # Enable verbose mode if -v or --verbose is passed
        -b|--branch) PLATFORM_IMAGE_BRANCH="$2"; shift ;;  # Capture platform_image_branch if provided
        *) CONFIG_PATH=$(realpath "$1") ;;  # Treat the first argument as the config path
    esac
    shift
done

# Check if config file is provided
if [ -z "$CONFIG_PATH" ]; then
    echo "Usage: $0 [-v|--verbose] [-b|--branch <branch_name>] /path/to/your/config.yml"
    exit 1
fi

# Check if config file exists
if [ ! -f "$CONFIG_PATH" ]; then
    echo "Config file not found at $CONFIG_PATH"
    exit 1
fi

echo "Using config file at $CONFIG_PATH"

# Model path
GENERATIVE_MODEL_FOLDER="gen-ai-models/"

# Warn if model file is not found
if [ ! -d "$GENERATIVE_MODEL_FOLDER" ]; then
    echo "WARNING: Model file not found at $GENERATIVE_MODEL_FOLDER. The playbook will proceed without it."
fi

GENERATIVE_MODEL_FOLDER=$(realpath "$GENERATIVE_MODEL_FOLDER")

# Search for docker_images folder with a prefix
DOCKER_IMAGES_PATH=$(find . -type d -name "docker_images-*" | head -n 1)

if [ -z "$DOCKER_IMAGES_PATH" ]; then
    echo "WARNING: No docker_images folder found with prefix 'docker_images-'. The playbook will proceed without it."
else
    DOCKER_IMAGES_PATH=$(realpath "$DOCKER_IMAGES_PATH")
    echo "Found docker images folder at $DOCKER_IMAGES_PATH"
fi

# Change directory to platform directory
cd "$(dirname "$0")/platform" || exit 1

# Warn if platform_image_branch was not provided and use default
if [ "$PLATFORM_IMAGE_BRANCH" == "release-test-main" ]; then
    echo "WARNING: No platform_image_branch specified. Using default 'release-test-main'."
fi

if [ "$VERBOSE" -eq 1 ]; then
    echo "Running in verbose mode (-vvvv)"
    ansible-playbook playbooks/test_deploy.yml --extra-vars "config_path=$CONFIG_PATH generative_model_folder=$GENERATIVE_MODEL_FOLDER docker_images=$DOCKER_IMAGES_PATH platform_image_branch=$PLATFORM_IMAGE_BRANCH" -vvvv
else
    ansible-playbook playbooks/test_deploy.yml --extra-vars "config_path=$CONFIG_PATH generative_model_folder=$GENERATIVE_MODEL_FOLDER docker_images=$DOCKER_IMAGES_PATH platform_image_branch=$PLATFORM_IMAGE_BRANCH"
fi
