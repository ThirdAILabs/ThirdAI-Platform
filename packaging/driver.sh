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
            elif [ -f /etc/redhat-release ]; then
                echo "Installing Ansible on CentOS/RHEL..."
                sudo dnf install -y ansible
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

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -v|--verbose) VERBOSE=1 ;;   # Enable verbose mode if -v or --verbose is passed
        *) CONFIG_PATH=$(realpath "$1") ;;  # Treat the first argument as the config path
    esac
    shift
done

# Check if config file is provided
if [ -z "$CONFIG_PATH" ]; then
    echo "Usage: $0 [-v|--verbose] /path/to/your/config.yml"
    exit 1
fi

# Check if config file exists
if [ ! -f "$CONFIG_PATH" ]; then
    echo "Config file not found at $CONFIG_PATH"
    exit 1
fi

echo "Using config file at $CONFIG_PATH"

# Model path
QWEN_MODEL_PATH="models/qwen2-0_5b-instruct-fp16.gguf"

# Warn if model file is not found
if [ ! -f "$QWEN_MODEL_PATH" ]; then
    echo "WARNING: Model file not found at $QWEN_MODEL_PATH. The playbook will proceed without it."
fi

QWEN_MODEL_FULL_PATH=$(realpath "$QWEN_MODEL_PATH")

# Change directory to platform directory
cd "$(dirname "$0")/platform" || exit 1

# Run Ansible playbook with or without verbose mode
if [ "$VERBOSE" -eq 1 ]; then
    echo "Running in verbose mode (-vvvv)"
    ansible-playbook playbooks/test_deploy.yml --extra-vars "config_path=$CONFIG_PATH qwen_model_path=$QWEN_MODEL_FULL_PATH" -vvvv
else
    ansible-playbook playbooks/test_deploy.yml --extra-vars "config_path=$CONFIG_PATH qwen_model_path=$QWEN_MODEL_FULL_PATH"
fi
