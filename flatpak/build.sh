#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Building and installing Stilo Notes Flatpak..."
flatpak-builder --user --install --force-clean build-dir io.github.fastrizwaan.StiloNotes.yaml

echo "Stilo Notes Flatpak built successfully! Run with:"
echo "flatpak run io.github.fastrizwaan.StiloNotes"
