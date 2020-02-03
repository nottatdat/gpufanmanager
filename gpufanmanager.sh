#!/bin/bash
cd $(dirname "$0")
source .env
rm -f "$GPU_MANAGER_SCRIPT".lock 
$GPU_MANAGER_SCRIPT
