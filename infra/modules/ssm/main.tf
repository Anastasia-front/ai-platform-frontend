locals {
  env_keys = nonsensitive(keys(var.env_values))
}

resource "aws_ssm_parameter" "env_vars" {
  for_each = toset(local.env_keys)

  name  = "/${var.project_name}-frontend/${each.key}"
  type  = "SecureString"
  value = var.env_values[each.key]
}

