#!/bin/bash
# Quick script to install Rust for Python 3.14+ compatibility

echo "Installing Rust for Python 3.14+ compatibility..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    if command -v brew &> /dev/null; then
        brew install rust
    else
        echo "Homebrew not found. Install Rust manually:"
        echo "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    fi
else
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
fi
echo "Rust installed. You may need to restart your terminal or run: source ~/.cargo/env"
