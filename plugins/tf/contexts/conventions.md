# Terraform/OpenTofu Conventions

## Tool Preference

- **Prefer OpenTofu** for new projects unless there are specific Terraform Enterprise requirements.
- **Use the existing tool** for existing projects — do not convert Terraform projects to OpenTofu or vice versa without explicit user direction.
- When writing examples or creating new configurations, default to OpenTofu-compatible syntax (which is compatible with both tools).

## Version

- **Check project files** for version constraints in `versions.tf` or `terraform.backend` blocks.
- **Default to** `>= 1.10` if no version constraint exists.
- Support Terraform 1.10+ and OpenTofu equivalents.

## Provider Configuration

- **Pin provider versions** with pessimistic constraints (`~>`):

✓ **Correct:**

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
```

✗ **Incorrect:**

```hcl
# Unpinned version
required_providers {
  aws = {
    source = "hashicorp/aws"
  }
}
```

- **Never hardcode credentials** in provider blocks. Use IAM roles/service principals, Vault/OpenBao, environment variables, or credential files.

## Module Structure

Organize files by purpose using standard naming conventions:

- `main.tf` — Primary resource definitions
- `variables.tf` — Input variable declarations
- `outputs.tf` — Output value declarations
- `providers.tf` — Provider configurations
- `versions.tf` — Terraform/provider version constraints
- `locals.tf` — Local values (when complex or numerous)
- `data.tf` — Data source definitions (when numerous)

For complex modules, group related resources into separate files (e.g., `network.tf`, `compute.tf`, `storage.tf`).

## Naming Conventions

- **Use `snake_case`** for resource names, variable names, and output names.
- **Use descriptive names** that indicate the resource type and purpose:

✓ **Correct:**

```hcl
resource "aws_s3_bucket" "application_logs" {
  bucket = "myapp-logs-${var.environment}"
}

variable "enable_encryption" {
  type = bool
}
```

✗ **Incorrect:**

```hcl
resource "aws_s3_bucket" "bucket1" {
  bucket = "logs"
}

variable "enc" {
  type = bool
}
```

- **Boolean variables and locals** should use `enable_` or `is_` prefixes.

## Variables

- **Always declare `type` and `description`** for all input variables:

✓ **Correct:**

```hcl
variable "instance_type" {
  type        = string
  description = "EC2 instance type for the application servers"
  default     = "t3.medium"
}

variable "availability_zones" {
  type        = list(string)
  description = "List of availability zones for subnet distribution"
}
```

✗ **Incorrect:**

```hcl
variable "instance_type" {
  default = "t3.medium"
}
```

- **Use validation blocks** for variables with constraints:

```hcl
variable "environment" {
  type        = string
  description = "Deployment environment"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}
```

- **Use specific types** over `any` whenever possible:

✓ **Correct:**

```hcl
variable "tags" {
  type        = map(string)
  description = "Resource tags"
  default     = {}
}
```

✗ **Incorrect:**

```hcl
variable "tags" {
  type    = any
  default = {}
}
```

## Outputs

- **Always include `description`** for output values:

✓ **Correct:**

```hcl
output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}
```

✗ **Incorrect:**

```hcl
output "vpc_id" {
  value = aws_vpc.main.id
}
```

- **Output only needed values** — avoid exposing internal implementation details.
- **Mark sensitive outputs** with `sensitive = true`:

```hcl
output "database_password" {
  description = "Database admin password"
  value       = random_password.db_password.result
  sensitive   = true
}
```

## Data Sources Over Hardcoding

Use data sources to look up existing infrastructure instead of hardcoding IDs/ARNs:

✓ **Correct:**

```hcl
data "aws_ami" "amazon_linux_2" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

resource "aws_instance" "app" {
  ami           = data.aws_ami.amazon_linux_2.id
  instance_type = var.instance_type
}
```

✗ **Incorrect:**

```hcl
resource "aws_instance" "app" {
  ami           = "ami-0c55b159cbfafe1f0"  # Hardcoded AMI ID
  instance_type = var.instance_type
}
```

## State Management

- **Use remote backends** with state locking for team collaboration:

```hcl
terraform {
  backend "s3" {
    bucket         = "myorg-terraform-state"
    key            = "prod/vpc/terraform.tfstate"
    region         = "us-west-2"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}
```

- **Never commit `.tfstate` files** to version control. Add to `.gitignore`:

```
# .gitignore
*.tfstate
*.tfstate.*
.terraform/
```

- **Separate state per environment** — use workspaces or separate backend configurations for dev/staging/prod.

## Security

- **Never store secrets in code or state** when avoidable. Use secret management services:

✓ **Correct:**

```hcl
data "aws_secretsmanager_secret_version" "db_password" {
  secret_id = "prod/db/password"
}

resource "aws_db_instance" "main" {
  password = data.aws_secretsmanager_secret_version.db_password.secret_string
}
```

- **Mark sensitive variables and outputs** with `sensitive = true`.
- **Review plans before apply** — always run `terraform plan` / `tofu plan` and review changes before applying.
- **Minimize IAM permissions** — grant least privilege access to resources.

## Formatting and Validation

- **Run `terraform fmt` / `tofu fmt`** before committing code to ensure consistent formatting.
- **Run `terraform validate` / `tofu validate`** to check syntax and internal consistency.
- Set up pre-commit hooks or CI checks to enforce formatting and validation.

## Testing

- **Use the built-in test framework** (`terraform test` / `tofu test`) with `.tftest.hcl` files:

```hcl
# tests/vpc.tftest.hcl
run "verify_vpc_cidr" {
  command = plan

  assert {
    condition     = aws_vpc.main.cidr_block == "10.0.0.0/16"
    error_message = "VPC CIDR block must be 10.0.0.0/16"
  }
}

run "verify_subnet_count" {
  command = plan

  assert {
    condition     = length(aws_subnet.private) == 3
    error_message = "Must have exactly 3 private subnets"
  }
}
```

- **Write behavioral assertions** that verify outcomes, not implementation details.
- **Test realistic scenarios** including edge cases and error conditions.

## Lifecycle Management

Use lifecycle meta-arguments to control resource behavior, and **always add a comment** explaining why:

✓ **Correct:**

```hcl
resource "aws_instance" "app" {
  ami           = data.aws_ami.app.id
  instance_type = var.instance_type

  # Prevent accidental instance replacement when AMI updates
  lifecycle {
    ignore_changes = [ami]
  }
}

resource "aws_s3_bucket" "critical_data" {
  bucket = "critical-data-${var.environment}"

  # Prevent accidental deletion of production data
  lifecycle {
    prevent_destroy = true
  }
}
```

✗ **Incorrect:**

```hcl
resource "aws_instance" "app" {
  # No explanation for lifecycle rule
  lifecycle {
    ignore_changes = [ami]
  }
}
```

- **`prevent_destroy`** — Prevent accidental deletion of critical resources.
- **`create_before_destroy`** — Create replacement before destroying old resource (for zero-downtime updates).
- **`ignore_changes`** — Ignore changes to specific attributes (use sparingly and document why).

## Expressions and Logic

- **Prefer `for_each` over `count`** for creating multiple similar resources, as it provides stable resource addresses:

✓ **Correct:**

```hcl
resource "aws_subnet" "private" {
  for_each = toset(var.availability_zones)

  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, index(var.availability_zones, each.value))
  availability_zone = each.value
}
```

✗ **Incorrect:**

```hcl
resource "aws_subnet" "private" {
  count = length(var.availability_zones)

  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index)
  availability_zone = var.availability_zones[count.index]
}
```

- **Use `locals` for repeated or complex expressions** to improve readability:

```hcl
locals {
  common_tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
    Project     = var.project_name
  }

  vpc_cidr_parts = split("/", var.vpc_cidr)
  vpc_prefix_length = parseint(local.vpc_cidr_parts[1], 10)
}

resource "aws_vpc" "main" {
  cidr_block = var.vpc_cidr
  tags       = merge(local.common_tags, { Name = "${var.project_name}-vpc" })
}
```

- **Use conditional expressions sparingly** — prefer explicit resource definitions over complex ternaries:

✓ **Acceptable:**

```hcl
resource "aws_instance" "app" {
  instance_type = var.environment == "prod" ? "t3.large" : "t3.medium"
}
```

✗ **Too complex:**

```hcl
resource "aws_instance" "app" {
  instance_type = var.environment == "prod" ? (var.high_traffic ? "t3.xlarge" : "t3.large") : (var.enable_dev_mode ? "t3.small" : "t3.medium")
}
```
