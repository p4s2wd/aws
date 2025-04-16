#!/bin/bash

# 运行 Terraform plan 并将输出保存到变量
plan_output=$(terraform plan)

# 定义颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# 输出原始 plan 输出
echo "$plan_output"

# 使用颜色显示 Plan summary
if [[ $plan_output =~ ([0-9]+)\ to\ add,\ ([0-9]+)\ to\ change,\ ([0-9]+)\ to\ destroy ]]; then
    add_count=${BASH_REMATCH[1]}
    change_count=${BASH_REMATCH[2]}
    destroy_count=${BASH_REMATCH[3]}
    
    printf "Plan: ${GREEN}%d to add${NC}, ${YELLOW}%d to change${NC}, ${RED}%d to destroy${NC}\n" "$add_count" "$change_count" "$destroy_count"
fi
