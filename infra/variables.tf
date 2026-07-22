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
  description = "CIDR ranges allowed to access the Nginx frontend over HTTP."
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

variable "nginx_origin_certificate" {
  type        = string
  description = "Cloudflare Origin Certificate for the frontend Nginx origin, supplied through Terraform variables or updated directly in SSM."
  sensitive   = true
}

variable "nginx_origin_certificate_version" {
  type        = number
  description = "Increment when rotating nginx_origin_certificate because value_wo is write-only."
  default     = 1
}

variable "nginx_origin_private_key" {
  type        = string
  description = "Cloudflare Origin private key for the frontend Nginx origin, supplied through Terraform variables or updated directly in SSM."
  sensitive   = true
}

variable "nginx_origin_private_key_version" {
  type        = number
  description = "Increment when rotating nginx_origin_private_key because value_wo is write-only."
  default     = 1
}
