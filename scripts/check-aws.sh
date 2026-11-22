#!/usr/bin/env bash
set -euo pipefail
if ! command -v aws >/dev/null 2>&1; then
  echo 'AWS CLI v2 required. Official install guide: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html'
  exit 1
fi
printf 'AWS CLI: '; aws --version
printf '\nSigned-in identity (contains account number; redact before sharing):\n'
aws sts get-caller-identity --output json
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-$(aws configure get region 2>/dev/null || true)}}"
if [[ -z "$REGION" ]]; then
  echo 'No default AWS region configured. Set AWS_REGION=us-west-2 (or your current region) before retrying.'
  exit 1
fi
printf '\nAWS Region: %s\n' "$REGION"
run_check() {
  local label="$1"; shift
  printf '\n-- %s --\n' "$label"
  if ! "$@"; then echo '(Could not list: insufficient permissions or unavailable API)'; fi
}
run_check 'ECS clusters' aws ecs list-clusters --region "$REGION" --query 'clusterArns' --output table
run_check 'ECR image repositories' aws ecr describe-repositories --region "$REGION" --query 'repositories[].repositoryName' --output table
run_check 'RDS database instances' aws rds describe-db-instances --region "$REGION" --query 'DBInstances[].[DBInstanceIdentifier,Engine,DBInstanceStatus]' --output table
run_check 'EC2 instances' aws ec2 describe-instances --region "$REGION" --query 'Reservations[].Instances[].[InstanceId,InstanceType,State.Name]' --output table
run_check 'Lightsail instances' aws lightsail get-instances --region "$REGION" --query 'instances[].[name,state.name]' --output table
