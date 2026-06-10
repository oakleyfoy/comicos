# Comicos Midtown Extension

This folder contains the Midtown browser extension scaffold used by the capture flow.

## What it does

- Detects when Comicos asks for a Midtown capture.
- Captures the currently open Midtown order detail page from the browser tab.
- Sends the captured HTML and order number back to Comicos for import.

## Production install

Set `VITE_MIDTOWN_EXTENSION_INSTALL_URL` in the web build environment to the Chrome Web Store listing URL.

## Local development

Load this folder as an unpacked extension in Chrome if you want to test the capture bridge locally.
