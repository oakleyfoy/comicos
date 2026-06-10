# Comicos Midtown Extension

This folder contains the Midtown Chrome extension used for first-time setup and capture.

## First-time setup

1. Set `VITE_MIDTOWN_EXTENSION_INSTALL_URL` in the web build environment to the Chrome Web Store listing URL.
2. Install the extension in Chrome.
3. Return to Comicos and refresh until the Midtown badge says `Extension connected`.
4. Open a Midtown order detail page and click `Capture Midtown Order`.

## What it does

- Detects when Comicos asks for a Midtown capture.
- Captures the currently open Midtown order detail page from the browser tab.
- Sends the captured HTML and order number back to Comicos for import.

## Local development

Load this folder as an unpacked extension in Chrome if you want to test the capture bridge locally.
