#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Building and installing Teddy Notes Flatpak..."
flatpak-builder --user --install --force-clean  --disable-rofiles-fuse build-dir io.github.fastrizwaan.TeddyNotes.yaml

echo "Teddy Notes Flatpak built successfully! Run with:"
echo "flatpak run io.github.fastrizwaan.TeddyNotes"
