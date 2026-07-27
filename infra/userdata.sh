#!/bin/bash
set -Eeuo pipefail

export DEBIAN_FRONTEND=noninteractive
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

apt-get update
apt-get upgrade -y

apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  gnupg \
  unzip \
  jq \
  nginx \
  docker.io

usermod -a -G docker ubuntu

systemctl enable docker
systemctl start docker

systemctl enable nginx
systemctl start nginx

install_aws_cli() {
  echo "Checking for existing AWS CLI installation..."

  if command -v aws >/dev/null 2>&1; then
    echo "AWS CLI already installed: $(aws --version)"
    return 0
  fi

  local arch
  arch="$(uname -m)"
  local aws_arch

  case "$arch" in
    x86_64)
      aws_arch="x86_64"
      ;;
    aarch64|arm64)
      aws_arch="aarch64"
      ;;
    *)
      echo "Unsupported architecture for AWS CLI installation: $arch" >&2
      return 1
      ;;
  esac

  echo "Detected architecture: $arch (AWS CLI arch: $aws_arch)"

  local tmp_dir
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' RETURN

  curl --fail --silent --show-error --location \
    "https://awscli.amazonaws.com/awscli-exe-linux-${aws_arch}.zip" \
    --output "${tmp_dir}/awscliv2.zip"

  unzip -q "${tmp_dir}/awscliv2.zip" -d "$tmp_dir"
  "${tmp_dir}/aws/install" --install-dir /usr/local/aws-cli --bin-dir /usr/local/bin

  echo "AWS CLI installed: $(aws --version)"
}

install_aws_cli
