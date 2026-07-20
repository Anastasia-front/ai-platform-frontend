variable "aws_region" {
  type = string
}

variable "project_name" {
  type = string
}

variable "key_name" {
  type = string
}

variable "ssh_allowed_cidrs" {
  description = "IPs allowed to SSH"
  type        = list(string)
}

variable "http_allowed_cidrs" {
  description = "CIDR ranges allowed to access the frontend over HTTP."
  type        = list(string)
}

variable "ec2_ami" {
  type = string
}

variable "frontend_instance_type" {
  type    = string
  default = "t3.micro"
}

variable "backend_base_api_url" {
  description = "Environment-specific backend API URL consumed by the Django frontend."
  type        = string
}

variable "google_client_id" {
  type        = string
  description = "OAuth client ID used by the frontend."
}

variable "env_values" {
  type      = map(string)
  sensitive = true
}

