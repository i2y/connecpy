#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REPO="i2y/connecpy"
BINARY_NAME="protoc-gen-connecpy"
DEFAULT_INSTALL_DIR="/usr/local/bin"

# Parse command line arguments and environment variables
INSTALL_DIR="${PROTOC_GEN_CONNECPY_INSTALL:-$DEFAULT_INSTALL_DIR}"
VERSION="${VERSION:-latest}"

# Function to print colored output
print_error() {
    echo -e "${RED}Error: $1${NC}" >&2
}

print_success() {
    echo -e "${GREEN}$1${NC}"
}

print_info() {
    echo -e "${YELLOW}$1${NC}"
}

# Detect OS
detect_os() {
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    case "$OS" in
        linux)
            echo "linux"
            ;;
        darwin)
            echo "darwin"
            ;;
        mingw*|msys*|cygwin*)
            echo "windows"
            ;;
        *)
            print_error "Unsupported operating system: $OS"
            exit 1
            ;;
    esac
}

# Detect architecture
detect_arch() {
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64|amd64)
            echo "amd64"
            ;;
        aarch64|arm64)
            echo "arm64"
            ;;
        *)
            print_error "Unsupported architecture: $ARCH"
            exit 1
            ;;
    esac
}

# Get the latest version from GitHub
get_latest_version() {
    curl -sL "https://api.github.com/repos/$REPO/releases/latest" | \
        grep '"tag_name":' | \
        sed -E 's/.*"([^"]+)".*/\1/'
}

# Main installation function
main() {
    print_info "Installing protoc-gen-connecpy..."
    
    # Detect system
    OS=$(detect_os)
    ARCH=$(detect_arch)
    
    print_info "Detected system: $OS/$ARCH"
    
    # Get version
    if [ "$VERSION" = "latest" ]; then
        VERSION=$(get_latest_version)
        if [ -z "$VERSION" ]; then
            print_error "Failed to get latest version"
            exit 1
        fi
    fi
    
    print_info "Installing version: $VERSION"
    
    # Construct download URL
    # Remove 'v' prefix from version for filename
    VERSION_NUM="${VERSION#v}"
    
    if [ "$OS" = "windows" ]; then
        ARCHIVE_NAME="${BINARY_NAME}_${VERSION_NUM}_${OS}_${ARCH}.zip"
        ARCHIVE_TYPE="zip"
    else
        ARCHIVE_NAME="${BINARY_NAME}_${VERSION_NUM}_${OS}_${ARCH}.tar.gz"
        ARCHIVE_TYPE="tar.gz"
    fi
    
    DOWNLOAD_URL="https://github.com/$REPO/releases/download/$VERSION/${ARCHIVE_NAME}"
    
    print_info "Downloading from: $DOWNLOAD_URL"
    
    # Create temporary directory
    TMP_DIR=$(mktemp -d)
    trap "rm -rf $TMP_DIR" EXIT
    
    # Download archive
    if ! curl -sL -o "$TMP_DIR/$ARCHIVE_NAME" "$DOWNLOAD_URL"; then
        print_error "Failed to download archive from $DOWNLOAD_URL"
        exit 1
    fi
    
    # Extract archive
    print_info "Extracting archive..."
    if [ "$ARCHIVE_TYPE" = "zip" ]; then
        if ! unzip -q "$TMP_DIR/$ARCHIVE_NAME" -d "$TMP_DIR"; then
            print_error "Failed to extract zip archive"
            exit 1
        fi
    else
        if ! tar -xzf "$TMP_DIR/$ARCHIVE_NAME" -C "$TMP_DIR"; then
            print_error "Failed to extract tar.gz archive"
            exit 1
        fi
    fi
    
    # Find the binary (it should be named protoc-gen-connecpy)
    if [ ! -f "$TMP_DIR/$BINARY_NAME" ]; then
        print_error "Binary not found in archive"
        exit 1
    fi
    
    # Make binary executable
    chmod +x "$TMP_DIR/$BINARY_NAME"
    
    # Create install directory if it doesn't exist
    if [ ! -d "$INSTALL_DIR" ]; then
        print_info "Creating directory: $INSTALL_DIR"
        if ! mkdir -p "$INSTALL_DIR" 2>/dev/null; then
            print_info "Need sudo to create $INSTALL_DIR"
            sudo mkdir -p "$INSTALL_DIR"
        fi
    fi
    
    # Install binary
    print_info "Installing to: $INSTALL_DIR/$BINARY_NAME"
    
    if [ -w "$INSTALL_DIR" ]; then
        mv "$TMP_DIR/$BINARY_NAME" "$INSTALL_DIR/$BINARY_NAME"
    else
        print_info "Need sudo to install to $INSTALL_DIR"
        sudo mv "$TMP_DIR/$BINARY_NAME" "$INSTALL_DIR/$BINARY_NAME"
    fi
    
    # Verify installation
    if [ -f "$INSTALL_DIR/$BINARY_NAME" ]; then
        print_success "✅ Successfully installed $BINARY_NAME $VERSION to $INSTALL_DIR"
        
        # Check if it's in PATH
        if command -v "$BINARY_NAME" >/dev/null 2>&1; then
            print_info "You can now use: protoc --connecpy_out=. your_service.proto"
        else
            print_info "Note: $INSTALL_DIR is not in your PATH"
            print_info "To use $BINARY_NAME from anywhere, add this directory to your PATH:"
            print_info "  echo 'export PATH=\"$INSTALL_DIR:\$PATH\"' >> ~/.bashrc"
            print_info "  source ~/.bashrc"
            print_info ""
            print_info "Or you can use the full path: $INSTALL_DIR/$BINARY_NAME"
        fi
    else
        print_error "Installation failed - binary not found at $INSTALL_DIR/$BINARY_NAME"
        exit 1
    fi
}

# Show usage
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    cat <<EOF
Install protoc-gen-connecpy

Usage:
    curl -sSL https://raw.githubusercontent.com/i2y/connecpy/main/install.sh | bash
    curl -sSL https://raw.githubusercontent.com/i2y/connecpy/main/install.sh | PROTOC_GEN_CONNECPY_INSTALL=\$HOME/.local/bin bash
    curl -sSL https://raw.githubusercontent.com/i2y/connecpy/main/install.sh | VERSION=v2.1.0 bash

Environment Variables:
    PROTOC_GEN_CONNECPY_INSTALL  Installation directory (default: /usr/local/bin)
    VERSION                       Version to install (default: latest)

Options:
    -h, --help                    Show this help message

Examples:
    # Install latest version to default location
    curl -sSL https://raw.githubusercontent.com/i2y/connecpy/main/install.sh | bash
    
    # Install to user directory
    curl -sSL https://raw.githubusercontent.com/i2y/connecpy/main/install.sh | PROTOC_GEN_CONNECPY_INSTALL=\$HOME/bin bash
    
    # Install specific version
    curl -sSL https://raw.githubusercontent.com/i2y/connecpy/main/install.sh | VERSION=v2.0.0 bash

EOF
    exit 0
fi

# Run main installation
main
