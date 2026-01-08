#!/bin/bash
# Quick script to run CopyLab API tests

# Check if API key is set
if [ -z "$COPYLAB_API_KEY" ]; then
    echo "⚠️  COPYLAB_API_KEY not set!"
    echo ""
    echo "Usage:"
    echo "  export COPYLAB_API_KEY='cl_yourapp_xxx...'"
    echo "  ./run_tests.sh"
    echo ""
    exit 1
fi

echo "Running CopyLab API tests..."
python tests/test_api.py
