variable "project_name" {
  type = string
}

variable "env_values" {
  type      = map(string)
  sensitive = true
}

variable "nginx_origin_certificate" {
  type      = string
  sensitive = true
}

variable "nginx_origin_certificate_version" {
  type = number
}

variable "nginx_origin_private_key" {
  type      = string
  sensitive = true
}

variable "nginx_origin_private_key_version" {
  type = number
}
