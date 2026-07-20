variable "project_name" {
  type = string
}

variable "ssh_allowed_cidrs" {
  type = list(string)
}

variable "http_allowed_cidrs" {
  type = list(string)
}

